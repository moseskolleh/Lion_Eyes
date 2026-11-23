# Reading the map

*November 2026. The map is the home page of the website; `floodwatch site` builds it.*

The map answers four questions, in this order: what today's outlook says, where
water goes, where slopes fail, and who and what is in the way. The layers panel
is grouped the same way.

## Warning colours

The outlook levels use the international colour code for public warnings: the
code in ISO 22324 (colour-coded alerts), used by WMO and national weather
services through the Common Alerting Protocol and by MeteoAlarm in Europe.

| Level | Word | Colour | What to do |
|---|---|---|---|
| LOW | Normal | green | No flood threat expected. |
| ELEVATED | Watch | yellow ("be aware") | Clear drains and gutters, watch the sky, check the next issue. |
| HIGH | Act | orange ("be prepared") | Be ready to move people from the lowest homes; watch hillsides. |

**Red is not used yet.** In the code it means "take action now": a warning that
flooding is imminent or under way. That is the hour-scale Warning tier
(storm tracking, lightning, residents' reports), which Lion Eyes does not issue
yet. Keeping red for it means the Outlook's HIGH, which comes up on about one
rainy-season day in six, does not wear red out.

The colours are the same in light and dark mode, and the level is always
written out too, for readers who do not see colour. In a Watch or Act outlook
the warning zones it names are filled with the level's colour.

## Hazard layers

Each colour family means one thing, so a colour on the map always says what
the ground is like:
- **Blue is water only.** This follows flood-zone maps such as the UK
  Environment Agency's: the darker the blue, the likelier the flooding.
- **Brown is steep, landslide-prone ground.**
- **Purple is people.** Population density uses a one-colour ramp (ColorBrewer
  "Purples") that clashes with neither the water blues nor the warning colours.
  The usual yellow-to-red population ramps would be mistaken for warnings here.
- **Dark grey marks things that are not hazards:** past-flood markers and
  facilities. A facility's ring takes the hazard colour of the ground it stands on.

| Layer | Drawn as | Meaning |
|---|---|---|
| Flood-prone ground | two blues: stronger where it floods first | **Floods first**: less than 1 m above the nearest stream or the shore. **Floods in heavy rain**: 1 to 3 m above. Heights come from the Copernicus 30 m terrain model (height above nearest drainage); about 57% of the flood-prone ground is in the first group |
| Streams | dark blue lines, thicker for bigger catchments | Drainage traced from the terrain |
| Past floods | dark grey circles with the number of floods | Places named in the flood history; the popup lists the floods and says when a place is approximate |
| Landslide-prone slopes | brown hatching | Steeper than 25 degrees: landslides, rockfalls and wall collapses are likelier |
| Buildings | blue on flood-prone ground, brown on steep slopes, grey elsewhere | Every footprint (Overture Maps), from zoom 14 |
| Roads that may flood | blue stretches of the main roads | Where they cross flood-prone ground |
| Health, schools, police | dark grey icons (the hospital "H", a book, a shield); a blue ring on flood-prone ground, brown on a steep slope | From zoom 14; places of worship (often used as shelters) from zoom 16 |
| Population density | five purples, labelled 5-25, 25-60, 60-120, 120-200 and 200+ people per hectare | Estimated from buildings (about 3.6 people each); a hectare is about the size of a football pitch |

**The map key** (bottom of the map; a "Map key" button on phones and small
screens) lists every layer now showing, with each colour or shade in words. It
changes as layers are switched on and off or appear with zoom. In a Watch or
Act outlook it adds the warning colour of the zones the outlook names.

The slider under "Base map" fades all hazard layers together; the base map can be
the street map (greyed so the hazard colours stand out), the Humanitarian
OpenStreetMap style, satellite imagery or none. Choices are remembered in the
browser.

## Searching

Type at least two letters in the search box (press `/` to jump to it). It looks
through past flood places, warning zones, main roads, and named clinics,
schools, police posts and places of worship, accents and small spelling
differences ignored. Use the arrow keys and Enter, or tap a result.

If what you want is not there, choose "Search OpenStreetMap": it asks
OpenStreetMap's Nominatim service, limited to the peninsula. It runs only when
you ask, as Nominatim's usage policy requires. Coordinates also work
(`8.4895, -13.2408`).

Tap or click anywhere on the map to see what is there: flood-prone ground, a
steep slope, and roughly how many people live nearby.

## Links

The address follows the map view (`#map=15/8.48950/-13.24080`), so a copied link
opens the same view. `index.html#place=Kroo Bay` opens a place and its flood
list; the flood history page uses these links ("Show on map"), and each flood
there has its own link (`floods.html#FT-20130808`).

## Where the past-flood places come from

`floodwatch places` places every name in the flood history with OpenStreetMap:
neighbourhoods first, then streets and landmarks whose name matches the report.
If streets of the same name lie more than 1.5 km apart, the name is left off
rather than guessed. 46 of the 109 names are on the map (November 2026); the
rest are too vague ("low-lying areas of Freetown") or not in OpenStreetMap
under that spelling. Results are in `data/derived/map_places.csv`.
