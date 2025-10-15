import logging
import os
import sys
from datetime import datetime, timedelta, timezone
import pathlib
import shutil
import zipfile

import eumdac
import imageio.v3 as iio
import tweepy
from satpy import Scene


logger = logging.getLogger(__name__)


class NoDataAvailable(RuntimeError):
    """Raised when no suitable SEVIRI products are available for the requested window."""
    pass

def download_latest_data(out_dir):
    consumer_key = os.environ["EUMETSAT_KEY"]
    consumer_secret = os.environ["EUMETSAT_SECRET"]

    token = eumdac.AccessToken((consumer_key, consumer_secret))
    datastore = eumdac.DataStore(token)

    collection = datastore.get_collection("EO:EUM:DAT:MSG:HRSEVIRI")

    today_utc = datetime.now(timezone.utc).date()
    yesterday = today_utc - timedelta(days=1)
    start = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    bbox = "-25.0,33.0,45.0,72.0"  # broad Europe region
    products = None
    for offset_hours in (0, 1, 2):
        attempt_start = start - timedelta(hours=offset_hours)
        attempt_end = end - timedelta(hours=offset_hours)
        logger.info(
            "Searching SEVIRI products between %s and %s (bbox=%s)",
            attempt_start.isoformat(),
            attempt_end.isoformat(),
            bbox,
        )
        products = collection.search(
            dtstart=attempt_start,
            dtend=attempt_end,
            bbox=bbox,
            sort="start,time,1",
        )
        if products.total_results > 0:
            logger.info(
                "Using %d products from window %s to %s",
                products.total_results,
                attempt_start.isoformat(),
                attempt_end.isoformat(),
            )
            break
        logger.warning(
            "No MSG SEVIRI data found between %s and %s, retrying with an additional one-hour offset.",
            attempt_start.isoformat(),
            attempt_end.isoformat(),
        )
    else:
        raise NoDataAvailable(
            "No MSG SEVIRI data found after checking the default window and two one-hour fallbacks."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    successful = 0
    for i, product in enumerate(products, 1):
        try:
            with product.open() as fsrc:
                dest = out_dir / fsrc.name
                with open(dest, "wb") as fdst:
                    shutil.copyfileobj(fsrc, fdst)
                logger.info("[%d/%d] Downloaded %s", i, products.total_results, fsrc.name)
                successful += 1
        except Exception as e:
            logger.warning("[%d] Failed to download %s: %s", i, product, e)

    if successful == 0:
        raise RuntimeError("Download attempt completed but no products were saved.")

def extract_and_generate(out_dir):
    extract_dir = out_dir / "extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Extracting archives into %s", extract_dir)

    for zf in out_dir.glob("*.zip"):
        with zipfile.ZipFile(zf, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

    nat_files = sorted(extract_dir.glob("*.nat"))
    rgb_dir = out_dir / "rgb_frames"
    if rgb_dir.exists():
        shutil.rmtree(rgb_dir)
    rgb_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Processing %d .nat files", len(nat_files))

    frames = []
    for nat in nat_files:
        try:
            scn = Scene(reader="seviri_l1b_native", filenames=[str(nat)])
            scn.load(["natural_color"])
            scn = scn.resample("msg_seviri_europe")  # cropped area
            out_png = rgb_dir / f"{nat.stem}.png"
            scn.save_dataset("natural_color", filename=str(out_png))
            frames.append(iio.imread(out_png))
        except Exception as e:
            logger.warning("Error processing %s: %s", nat.name, e)

    if not frames:
        raise RuntimeError("No frames generated from extracted data.")

    gif_path = out_dir / "Meteosat_Europe.gif"
    iio.imwrite(gif_path, frames, duration=0.25)
    logger.info("GIF saved to %s", gif_path)
    return gif_path

def post_to_x(message, gif_path=None):
    consumer_key = os.environ["X_API_KEY"]
    consumer_secret = os.environ["X_API_SECRET"]
    access_token = os.environ["X_ACCESS_TOKEN"]
    access_secret = os.environ["X_ACCESS_SECRET"]

    auth = tweepy.OAuth1UserHandler(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    media_id = None
    if gif_path is not None:
        api_v1 = tweepy.API(auth)
        logger.info("Uploading media %s", gif_path)
        media = api_v1.media_upload(filename=str(gif_path))
        media_id = media.media_id_string

    client = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    payload = {"text": message}
    if media_id:
        payload["media_ids"] = [media_id]
    client.create_tweet(**payload)
    logger.info("Post published successfully.")

if __name__ == "__main__":
    SUCCESS_MESSAGE = (
        "Meteosat SEVIRI view over Europe\n"
        "Data (c) EUMETSAT\n"
        "#Meteosat #EUMETSAT #EarthObservation"
    )
    FALLBACK_MESSAGE = (
        "Meteosat Europe update: no new SEVIRI imagery available today. "
        "We will be back with fresh data soon. #Meteosat #EUMETSAT"
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    out_dir = pathlib.Path("downloads")
    gif_path = None
    try:
        download_latest_data(out_dir)
        gif_path = extract_and_generate(out_dir)
        post_to_x(SUCCESS_MESSAGE, gif_path=gif_path)
    except NoDataAvailable as exc:
        logger.warning("No data available: %s", exc)
        post_to_x(FALLBACK_MESSAGE)
    except Exception as exc:
        logger.exception("Workflow failed: %s", exc)
        sys.exit(1)
    finally:
        if out_dir.exists():
            try:
                shutil.rmtree(out_dir)
                logger.info("Removed temporary directory %s", out_dir)
            except Exception as cleanup_err:
                logger.warning("Failed to remove temporary directory %s: %s", out_dir, cleanup_err)
