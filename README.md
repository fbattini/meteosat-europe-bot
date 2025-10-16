# Europe From Space - Meteosat Europe Bot

**Automatic daily satellite animation of Europe from EUMETSAT’s Meteosat SEVIRI.**  
Generated and posted every morning (hopefully) to show yesterday’s clouds, snow, and sunlight from 36,000 km above 🌍  

**Follow on X (Twitter):** [@EuropeFromSpace](https://x.com/EuropeFromSpace)  
**Data:** © [EUMETSAT](https://www.eumetsat.int)  
**Processing:** [Satpy](https://satpy.readthedocs.io) & [EUMDAC](https://user.eumetsat.int/resources/user-guides/eumetsat-data-access-client-eumdac-guide)  
**Automation:** [GitHub Actions](https://github.com/features/actions)

---

### Example output
Below is an example Meteosat SEVIRI *Natural Color Composite* animation of Europe:

<p align="center">
  <img src="docs/example.gif" width="820" alt="Meteosat Europe Natural Colour RGB Example">
</p>

---

### How it works
1. Retrieves yesteday's **Meteosat SEVIRI** L1.5 data via the **EUMETSAT Data Store API**  
2. Processes it into natural color composites using **Satpy**  
3. Generates a **daily animation GIF**  
4. Posts it automatically on [X](https://x.com/EuropeFromSpace) via the **Twitter API**

---

### License
This repository’s code is released under the **MIT License**,  
while data and imagery are © **EUMETSAT** and subject to their data policy.
