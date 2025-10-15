import logging
import os
import sys
from datetime import datetime, timedelta, timezone
import pathlib
import shutil
import tempfile
import zipfile
import warnings

import eumdac
import imageio.v3 as iio
import tweepy
from satpy import Scene
from pyresample import create_area_def


logger = logging.getLogger(__name__)

warnings.filterwarnings(
    "ignore",
    message="invalid value encountered",
    category=RuntimeWarning,
)


class NoDataAvailable(RuntimeError):
    """Raised when no suitable SEVIRI products are available for the requested window."""
    pass


EUROPE_AREA = create_area_def(
    "meteosat_europe_latlon",
    {"proj": "latlong"},
    area_extent=(-25.0, 32.0, 45.0, 70.0),
    resolution=(0.05, 0.05),
)

# Process only one scene every N products to keep runtime manageable.
PRODUCT_SAMPLE_STEP = 1


def find_products():
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
            return products, products.total_results
        logger.warning(
            "No MSG SEVIRI data found between %s and %s, retrying with an additional one-hour offset.",
            attempt_start.isoformat(),
            attempt_end.isoformat(),
        )
    raise NoDataAvailable(
        "No MSG SEVIRI data found after checking the default window and two one-hour fallbacks."
    )


def extract_and_generate(products, total_results, out_dir, sample_step=PRODUCT_SAMPLE_STEP):
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []

    if sample_step > 1:
        logger.info(
            "Processing every %dth product (%d total available)",
            sample_step,
            total_results,
        )
    else:
        logger.info("Processing every product (%d total available)", total_results)

    for index, product in enumerate(products, start=1):
        if (index - 1) % sample_step != 0:
            logger.debug(
                "Skipping product %d/%d due to sampling (step=%d)",
                index,
                total_results,
                sample_step,
            )
            continue
        with tempfile.TemporaryDirectory(dir=out_dir) as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            zip_path = tmp_path / "product.zip"
            try:
                with product.open() as fsrc, open(zip_path, "wb") as fdst:
                    shutil.copyfileobj(fsrc, fdst)
                    name = getattr(fsrc, "name", f"product_{index}.zip")
                logger.info("[%d/%d] Downloaded %s", index, total_results, name)
            except Exception as exc:
                logger.warning("[%d/%d] Failed to download product %s: %s", index, total_results, product, exc)
                continue

            try:
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(tmp_path)
            except zipfile.BadZipFile as exc:
                logger.warning("Skipping corrupted archive %s: %s", name, exc)
                continue

            nat_files = sorted(tmp_path.glob("*.nat"))
            if not nat_files:
                logger.warning("No .nat files found in archive %s", name)
                continue

            for nat in nat_files:
                try:
                    scn = Scene(reader="seviri_l1b_native", filenames=[str(nat)])
                    scn.load(["natural_color"])
                    scn = scn.resample(EUROPE_AREA)
                    out_png = tmp_path / f"{nat.stem}.png"
                    scn.save_dataset("natural_color", filename=str(out_png))
                    frames.append(iio.imread(out_png))
                except Exception as exc:
                    logger.warning("Error processing %s: %s", nat.name, exc)

    if not frames:
        raise RuntimeError("No frames generated from extracted data.")

    gif_path = out_dir / "Meteosat_Europe.gif"
    iio.imwrite(gif_path, frames, duration=0.25, loop=0)
    logger.info(
        "GIF saved to %s using %d frames out of %d products (step=%d)",
        gif_path,
        len(frames),
        total_results,
        sample_step,
    )
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
        products, total_results = find_products()
        gif_path = extract_and_generate(products, total_results, out_dir)
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
