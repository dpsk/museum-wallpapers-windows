import contextlib
import http.client
import io
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from helpers import FakePlatform, Monitor, make_jpeg
from helpers import core as museum
from museum_wallpapers import strings

CONFIG = museum.normalize_config({})
SCREEN = (3840, 2160)


def claim(prop, value):
    return {prop: [{"mainsnak": {"datavalue": {"value": value}}}]}


class ConfigTest(unittest.TestCase):
    def test_settings_file_is_read(self):
        self.assertEqual(museum.config_entry(json.dumps({"caption": "bottom-left"}))["caption"], "bottom-left")

    def test_plugin_placard_key_is_accepted(self):
        self.assertEqual(museum.config_entry(json.dumps({"placard": "top-left"}))["caption"], "top-left")
        entry = museum.config_entry(json.dumps({"placard": "top-left", "caption": "off"}))
        self.assertEqual(entry["caption"], "off")

    def test_missing_or_broken_settings_give_defaults(self):
        self.assertEqual(museum.config_entry("not json"), {})
        self.assertEqual(museum.config_entry(json.dumps(["nope"])), {})
        self.assertEqual(museum.normalize_config({})["intervalMinutes"], 60)

    def test_values_are_normalized(self):
        config = museum.normalize_config({
            "intervalMinutes": "-5", "caption": "middle", "language": "RU",
            "notifyOnChange": "yes", "cacheSize": 0, "saveDir": "~/Art",
            "filters": {"artists": "Claude Monet", "yearFrom": "1850", "genres": ["", "landscape"]},
        })
        self.assertEqual(config["intervalMinutes"], 0)
        self.assertEqual(config["caption"], "bottom-right")
        self.assertEqual(config["language"], "ru")
        self.assertFalse(config["notifyOnChange"])
        self.assertEqual(config["cacheSize"], 2)
        self.assertEqual(config["saveDir"], os.path.realpath(Path.home() / "Art"))
        self.assertEqual(config["filters"]["artists"], ["Claude Monet"])
        self.assertEqual(config["filters"]["yearFrom"], 1850)
        self.assertEqual(config["filters"]["genres"], ["landscape"])

    def test_filter_key_is_stable(self):
        a = museum.normalize_filters({"artists": ["Q296"]})
        b = museum.normalize_filters({"artists": ["Q296"]})
        self.assertEqual(museum.filter_key(a), museum.filter_key(b))
        self.assertNotEqual(museum.filter_key(a), museum.filter_key(museum.normalize_filters({})))


class OverrideTest(unittest.TestCase):
    def test_popup_filter_replaces_configured_filter(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, mock.patch.object(museum, "STATE", Path(tmp)):
            config = museum.normalize_config({"filters": {"artists": ["Rembrandt"]}})
            self.assertEqual(museum.active_filters(config)["artists"], ["Rembrandt"])
            museum.write_json(Path(tmp) / "filter.json", {"artists": [{"id": "Q296", "label": "Claude Monet"}]})
            active = museum.active_filters(config)
            self.assertEqual(active["artists"], ["Q296"])
            self.assertEqual(active["movements"], [])


class PickingTest(unittest.TestCase):
    def test_landscape_scan_is_usable(self):
        self.assertTrue(museum.usable("File:A - Google Art Project.jpg", 6271, 4332, CONFIG, SCREEN))
        self.assertTrue(museum.usable("File:Wide.jpg", 7600, 3800, CONFIG, SCREEN))

    def test_portrait_panorama_small_and_tiles_are_not(self):
        self.assertFalse(museum.usable("File:Portrait.jpg", 4413, 5338, CONFIG, SCREEN))
        self.assertFalse(museum.usable("File:Saudade.jpg", 29696, 1254, CONFIG, SCREEN))
        self.assertFalse(museum.usable("File:Small.jpg", 2048, 1400, CONFIG, SCREEN))
        self.assertFalse(museum.usable("File:Stuart - Google Art Project-x0-y2.jpg", 3840, 2505, CONFIG, SCREEN))
        self.assertFalse(museum.usable("File:Empty.jpg", 0, 0, CONFIG, SCREEN))

    def test_smaller_screen_accepts_smaller_scans(self):
        self.assertTrue(museum.usable("File:Small.jpg", 2048, 1300, CONFIG, (1920, 1080)))

    def test_year_range(self):
        filters = museum.normalize_filters({"yearFrom": 1850, "yearTo": 1900})
        self.assertTrue(museum.year_matches(1873, filters))
        self.assertFalse(museum.year_matches(1901, filters))
        self.assertFalse(museum.year_matches(None, filters))
        self.assertTrue(museum.year_matches(None, museum.normalize_filters({})))

    def test_sparql_combines_filters(self):
        query = museum.sparql_query(museum.normalize_filters(
            {"artists": ["Q296"], "movements": ["Q40415"], "genres": ["Q191163"], "yearFrom": 1870}))
        self.assertIn("VALUES ?artist { wd:Q296 }", query)
        self.assertIn("UNION { ?p wdt:P170 ?creator. ?creator wdt:P135 ?movement }", query)
        self.assertIn("VALUES ?genre { wd:Q191163 }", query)
        self.assertIn("FILTER(YEAR(?date) >= 1870)", query)
        self.assertNotIn("<=", query)

    def test_commons_file_title_from_sparql_url(self):
        url = "http://commons.wikimedia.org/wiki/Special:FilePath/Claude%20Monet%20-%20L%27%C3%89t%C3%A9.jpg"
        self.assertEqual(museum.file_title_from_url(url), "File:Claude Monet - L'Été.jpg")

    def test_genre_names_resolve_without_network(self):
        self.assertEqual(museum.resolve("Landscape", "genre"), "Q191163")
        self.assertEqual(museum.resolve("Q296", "artist"), "Q296")


class WikidataTest(unittest.TestCase):
    def test_claims_and_years(self):
        entity = {"claims": {**claim("P31", {"id": "Q3305213"}), **claim("P571", {"time": "+1873-00-00T00:00:00Z"})}}
        self.assertTrue(museum.is_painting(entity))
        self.assertEqual(museum.claim_year(entity), 1873)
        self.assertEqual(museum.claim_year({"claims": claim("P571", {"time": "-0350-00-00T00:00:00Z"})}), -350)

    def test_commons_media_info_uses_statements(self):
        media = {"statements": claim("P6243", {"id": "Q23758876"})}
        self.assertEqual(museum.claim_ids(media, "P6243"), ["Q23758876"])

    def test_label_falls_back_to_any_language(self):
        entity = {"labels": {"de": {"value": "Stürmische See im Abendrot"}}}
        self.assertEqual(museum.label(entity, "en"), "Stürmische See im Abendrot")
        self.assertEqual(museum.label({"labels": {"mul": {"value": "X"}, "de": {"value": "Y"}}}, "en"), "X")

    def test_object_name_drops_quickstatements(self):
        raw = ('German: Stürmische See im Abendrot. title QS:P1476,de:"Stürmische See im Abendrot." '
               'label QS:Lde,"Stürmische See im Abendrot."')
        self.assertEqual(museum.object_name(raw), "Stürmische See im Abendrot")
        self.assertEqual(museum.object_name("The Ninth Wave"), "The Ninth Wave")
        self.assertEqual(museum.object_name("Nocturne: Blue and Silver – Chelsea"), "Nocturne: Blue and Silver – Chelsea")
        self.assertEqual(museum.object_name("German: Die Welle English: The Wave"), "The Wave")
        self.assertEqual(museum.object_name("Norwegian Bokmål: Skrik"), "Skrik")
        self.assertEqual(museum.object_name("The English: A Portrait"), "The English: A Portrait")
        self.assertIsNone(museum.object_name(""))

    def test_long_object_names_end_on_a_word(self):
        name = ("The Disembarkation of Christopher Columbus with Companions on Three Launches, "
                "on Friday 12th October 1492, At Sunrise, on an American Island")
        short = museum.object_name(name)
        self.assertTrue(short.endswith("At Sunrise…"), short)
        self.assertLessEqual(len(short), 121)

    def test_scan_dates_are_not_painting_years(self):
        self.assertEqual(museum.painting_date("10 April 2008"), "")
        self.assertEqual(museum.painting_date("<time>2012-03-01</time>"), "")
        self.assertEqual(museum.painting_date("circa 1873"), "circa 1873")
        self.assertEqual(museum.painting_date("1873–1875"), "1873–1875")
        self.assertEqual(museum.painting_date("1910, photographed 2009"), "1910, photographed 2009")
        self.assertEqual(museum.painting_date(""), "")

    def test_commons_description_without_quickstatements(self):
        raw = ('Reval (Tallinn) label QS:Len,"Reval (Tallinn)" label QS:Lde,"Reval (heute Tallinn) in Estland" '
               'label QS:Lru,"Ревель (Таллин)"')
        self.assertEqual(museum.without_quickstatements(raw), "Reval (Tallinn)")
        self.assertEqual(museum.commons_description(raw), "")
        long = "A calm evening over the harbour, with fishing boats returning under a pale yellow sky."
        self.assertEqual(museum.commons_description(long), long)

    def test_label_and_article_fall_back_to_english(self):
        entity = {"labels": {"en": {"value": "The Hay Wain"}}, "sitelinks": {"enwiki": {"title": "The Hay Wain"}}}
        self.assertEqual(museum.label(entity, "ru"), "The Hay Wain")
        self.assertEqual(museum.article(entity, "ru"), ("en", "The Hay Wain"))
        self.assertIsNone(museum.article({}, "en"))


class TextTest(unittest.TestCase):
    def test_plain_strips_markup(self):
        self.assertEqual(museum.plain('<div class="fn">Man of <b>War</b> &amp; Rocks</div>'), "Man of War & Rocks")
        self.assertEqual(museum.plain("one two three", 8), "one two…")

    def test_first_sentences(self):
        text = "First one. Second one! Third? Fourth."
        self.assertEqual(museum.first_sentences(text, 2), "First one. Second one!")
        self.assertEqual(museum.first_sentences("Painted c. 1870 in St. Petersburg. Next.", 1),
                         "Painted c. 1870 in St. Petersburg.")
        self.assertEqual(museum.first_sentences("By J. M. W. Turner. Next.", 1), "By J. M. W. Turner.")

    def test_parse_years(self):
        self.assertEqual(museum.parse_years("1850-1900"), (1850, 1900))
        self.assertEqual(museum.parse_years("1850-"), (1850, None))
        self.assertEqual(museum.parse_years("-1900"), (None, 1900))
        with self.assertRaises(ValueError):
            museum.parse_years("eighteen fifty")

    def test_credit_line(self):
        line = museum.credit_line("monet.jpg", {"artist": "Claude Monet", "title": "Poppies", "year": "1873",
                                                "commons": "https://commons.wikimedia.org/wiki/File:X.jpg"})
        self.assertEqual(line, "| monet.jpg | Claude Monet, *Poppies*, 1873 "
                               "([source](https://commons.wikimedia.org/wiki/File:X.jpg)) |\n")

    def test_local_credit_reads_credits_table(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            folder = Path(tmp)
            (folder / "CREDITS.md").write_text("| File | Painting |\n| --- | --- |\n"
                                               "| hay.jpg | John Constable, *The Hay Wain*, 1821 |\n")
            self.assertEqual(museum.local_credit(folder / "hay.jpg"), "John Constable, The Hay Wain, 1821")
            self.assertIsNone(museum.local_credit(folder / "other.jpg"))


class EdgeCaseTest(unittest.TestCase):
    def test_fit_setting(self):
        self.assertEqual(museum.normalize_config({})["fit"], "blur")
        self.assertEqual(museum.normalize_config({"fit": "wall"})["fit"], "wall")
        self.assertEqual(museum.normalize_config({"fit": "stretch"})["fit"], "blur")

    def test_fame_setting(self):
        self.assertEqual(museum.normalize_config({})["fame"], "famous")
        self.assertEqual(museum.normalize_config({"fame": "known"})["fame"], "known")
        self.assertEqual(museum.normalize_config({"fame": "legendary"})["fame"], "famous")

    def test_fame_is_part_of_the_queue_key(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, mock.patch.object(museum, "STATE", Path(tmp)):
            famous = museum.queue_key(museum.normalize_config({"fame": "famous"}))
            self.assertNotEqual(famous, museum.queue_key(museum.normalize_config({"fame": "any"})))

    def test_fame_list_goes_into_the_pool_query(self):
        filters = museum.normalize_filters({"movements": ["Q40415"]})
        filters["fameArtists"] = ["Q5582", "Q41264"]
        query = museum.sparql_query(filters)
        self.assertIn("VALUES ?famed { wd:Q5582 wd:Q41264 } ?p wdt:P170 ?famed.", query)
        self.assertTrue(museum.has_entity_filters(filters))
        filters["fameArtists"] = ["Q1 }"]
        with self.assertRaises(ValueError):
            museum.sparql_query(filters)

    def test_named_artists_skip_the_fame_list(self):
        config = museum.normalize_config({"fame": "famous"})
        with mock.patch.object(museum, "active_filters", return_value=museum.normalize_filters({"artists": ["Q296"]})), \
             mock.patch.object(museum, "famous_painters") as famous, \
             mock.patch.object(museum, "screen_size", return_value=SCREEN), \
             mock.patch.object(museum, "filtered_candidates", side_effect=museum.NoMatch("stop")):
            with self.assertRaises(museum.NoMatch):
                museum.fetch_next(config)
        famous.assert_not_called()

    def test_an_empty_painter_list_is_not_cached(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, mock.patch.object(museum, "CACHE", Path(tmp)), \
             mock.patch.object(museum, "http_json", return_value={"results": {"bindings": []}}):
            with self.assertRaises(ValueError):
                museum.famous_painters(60)
            self.assertFalse((Path(tmp) / "pools" / "fame-60.json").exists())

    def test_crop_fraction(self):
        self.assertAlmostEqual(museum.crop_fraction(3840, 2160, SCREEN), 0)
        self.assertAlmostEqual(museum.crop_fraction(5090, 3420, SCREEN), 0.163, places=3)

    def test_bad_caption_type_does_not_crash(self):
        self.assertEqual(museum.normalize_config({"caption": []})["caption"], "bottom-right")
        self.assertEqual(museum.normalize_config({"caption": "off"})["caption"], "off")

    def test_sparql_rejects_non_ids(self):
        with self.assertRaises(ValueError):
            museum.sparql_query(museum.normalize_filters({"artists": ["Q1 } ?x ?y ?z {"]}))

    def test_empty_popup_filter_is_ignored(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, mock.patch.object(museum, "STATE", Path(tmp)):
            museum.write_json(Path(tmp) / "filter.json", {"artists": [], "movements": [], "genres": [],
                                                          "yearFrom": None, "yearTo": None})
            self.assertIsNone(museum.override_filters())

    def test_pipes_survive_the_credits_table(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            folder = Path(tmp)
            info = {"artist": "A", "title": "Left | Right", "commons": "https://example.org/x"}
            (folder / "CREDITS.md").write_text("| File | Painting |\n| --- | --- |\n" + museum.credit_line("x.jpg", info))
            self.assertEqual(museum.local_credit(folder / "x.jpg"), "A, Left | Right")


class FameBundleTest(unittest.TestCase):
    """The painters of a fame level and their paintings: built-in copy first,
    refreshed in the background, an old copy used while it refreshes."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.cache = Path(tmp.name) / "cache"
        self.seed = Path(tmp.name) / "seed"
        for patcher in (mock.patch.object(museum, "CACHE", self.cache), mock.patch.object(museum, "SEED", self.seed),
                        mock.patch.dict(museum._fame_memory, clear=True), mock.patch.dict(museum._refreshing, clear=True),
                        mock.patch.dict(museum._refresh_failed, clear=True)):
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def bundle(tag, at=None):
        return {"at": time.time() if at is None else at, "level": 60, "painters": [f"Q{tag}"],
                "items": [[f"Q{tag}0", f"File:{tag}.jpg"]]}

    def write_seed(self, bundle):
        import gzip
        self.seed.mkdir(parents=True, exist_ok=True)
        with gzip.open(museum.seed_path(60), "wt", encoding="utf-8") as handle:
            json.dump(bundle, handle)

    def wait_for_refresh(self):
        thread = museum._refreshing.get(60)
        if thread:
            thread.join(10)

    def test_the_built_in_copy_is_used_at_once_and_refreshed_behind(self):
        self.write_seed(self.bundle(1, at=0))
        started, release = threading.Event(), threading.Event()

        def slow_wikidata(level):
            started.set()
            release.wait(5)
            return self.bundle(2)

        with mock.patch.object(museum, "build_fame_bundle", side_effect=slow_wikidata):
            self.assertEqual(museum.famous_painters(60), ["Q1"])  # no wait for Wikidata
            self.assertTrue(started.wait(5))
            self.assertEqual(museum.fame_bundle(60)["painters"], ["Q1"])  # still refreshing
            release.set()
            self.wait_for_refresh()
        self.assertEqual(museum.fame_bundle(60)["painters"], ["Q2"])
        self.assertEqual(json.loads(museum.fame_path(60).read_text())["items"], [["Q20", "File:2.jpg"]])

    def test_an_old_copy_is_used_while_it_refreshes(self):
        museum.write_json(museum.fame_path(60), self.bundle(1, at=time.time() - museum.POOL_MAX_AGE - 5))
        with mock.patch.object(museum, "build_fame_bundle", return_value=self.bundle(2)) as build:
            self.assertEqual(museum.famous_painters(60), ["Q1"])
            self.wait_for_refresh()
            build.assert_called_once_with(60)
        self.assertEqual(museum.famous_painters(60), ["Q2"])

    def test_a_fresh_copy_is_not_refreshed(self):
        museum.write_json(museum.fame_path(60), self.bundle(1))
        self.write_seed(self.bundle(9))
        with mock.patch.object(museum, "build_fame_bundle") as build:
            self.assertEqual(museum.famous_painters(60), ["Q1"])
        build.assert_not_called()
        self.assertNotIn(60, museum._refreshing)

    def test_without_any_copy_the_pick_waits_for_wikidata(self):
        with mock.patch.object(museum, "build_fame_bundle", return_value=self.bundle(3)) as build:
            self.assertEqual(museum.famous_painters(60), ["Q3"])
            build.assert_called_once_with(60)
        self.assertNotIn(60, museum._refreshing)
        self.assertTrue(museum.fame_path(60).exists())

    def test_a_failed_refresh_keeps_the_old_copy_and_waits_before_retrying(self):
        self.write_seed(self.bundle(1))
        with mock.patch.object(museum, "build_fame_bundle", side_effect=ValueError("broken JSON")) as build, \
             contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(museum.famous_painters(60), ["Q1"])
            self.wait_for_refresh()
            self.assertEqual(museum.famous_painters(60), ["Q1"])
            self.wait_for_refresh()
        self.assertEqual(build.call_count, 1)
        self.assertIn("refreshing the painter list failed", err.getvalue())
        self.assertFalse(museum.fame_path(60).exists())

    def test_a_broken_cached_copy_falls_back_to_the_built_in_one(self):
        museum.fame_path(60).parent.mkdir(parents=True)
        museum.fame_path(60).write_text("{\"at\": 1, \"painters\": [")
        self.write_seed(self.bundle(1))
        with mock.patch.object(museum, "build_fame_bundle", return_value=self.bundle(2)):
            self.assertEqual(museum.famous_painters(60), ["Q1"])
            self.wait_for_refresh()

    def test_building_asks_for_painters_then_their_paintings(self):
        answers = [{"results": {"bindings": [{"famed": {"value": "http://www.wikidata.org/entity/Q5582"}}]}},
                   {"results": {"bindings": [{"p": {"value": "http://www.wikidata.org/entity/Q45585"},
                                              "img": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/The%20Starry_Night.jpg"}}]}}]
        with mock.patch.object(museum, "http_json", side_effect=answers) as http:
            bundle = museum.build_fame_bundle(60)
        self.assertEqual(bundle["painters"], ["Q5582"])
        self.assertEqual(bundle["items"], [["Q45585", "File:The Starry Night.jpg"]])
        self.assertIn("FILTER(?links >= 60)", http.call_args_list[0].kwargs["data"]["query"])
        self.assertIn("VALUES ?famed { wd:Q5582 }", http.call_args_list[1].kwargs["data"]["query"])

    def test_fame_alone_picks_from_the_bundle_pool(self):
        self.write_seed(self.bundle(1))
        config = museum.normalize_config({"fame": "famous"})
        seen = {}

        def candidates(filters, config, screen):
            seen["filters"] = dict(filters)
            seen["pool"] = museum.entity_pool(filters)
            raise museum.NoMatch("stop")

        with mock.patch.object(museum, "active_filters", return_value=museum.normalize_filters({})), \
             mock.patch.object(museum, "build_fame_bundle", return_value=self.bundle(2)), \
             mock.patch.object(museum, "query_pool") as query, \
             mock.patch.object(museum, "screen_size", return_value=SCREEN), \
             mock.patch.object(museum, "filtered_candidates", side_effect=candidates):
            with self.assertRaises(museum.NoMatch):
                museum.fetch_next(config)
            self.wait_for_refresh()
        query.assert_not_called()
        self.assertEqual(seen["pool"], [["Q10", "File:1.jpg"]])
        self.assertNotIn("fameArtists", seen["filters"])

    def test_fame_with_years_queries_with_the_bundle_painters(self):
        museum.write_json(museum.fame_path(60), self.bundle(1))
        config = museum.normalize_config({"fame": "famous"})
        with mock.patch.object(museum, "active_filters", return_value=museum.normalize_filters({"yearFrom": 1800})), \
             mock.patch.object(museum, "query_pool", return_value=[["Q7", "File:7.jpg"]]) as query, \
             mock.patch.object(museum, "screen_size", return_value=SCREEN), \
             mock.patch.object(museum, "image_infos", return_value={}), \
             mock.patch.dict(museum._pools, clear=True):
            with self.assertRaises(museum.NoMatch):
                museum.fetch_next(config)
        self.assertEqual(query.call_args.args[0]["fameArtists"], ["Q1"])
        self.assertEqual(query.call_args.args[0]["yearFrom"], 1800)


class SwitchTest(unittest.TestCase):
    """switch() and fetch_next() against temporary state, without network."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(os.path.realpath(self.tmp.name))
        self.cache, self.state = root / "cache", root / "state"
        self.cache.mkdir()
        self.platform = FakePlatform()
        self.patches = [
            mock.patch.object(museum, "CACHE", self.cache),
            mock.patch.object(museum, "QUEUE", self.cache / "queue"),
            mock.patch.object(museum, "DISPLAY", self.cache / "display"),
            mock.patch.object(museum, "STATE", self.state),
            mock.patch.object(museum, "PLATFORM", self.platform),
            mock.patch.object(museum, "screen_size", return_value=SCREEN),
            mock.patch.object(museum, "spawn_notify"),
        ]
        for patch in self.patches:
            patch.start()
        # Framing and the caption have their own tests; here the painting is shown as is.
        self.config = museum.normalize_config({"saveDir": str(root / "saved"), "fit": "cover", "fame": "any",
                                               "caption": "off"})

    def tearDown(self):
        mock.patch.stopall()
        self.tmp.cleanup()

    def set_link(self, target):
        self.platform.current = Path(target)

    def test_truncated_download_is_recorded_not_raised(self):
        with mock.patch.object(museum, "fetch_next", side_effect=http.client.IncompleteRead(b"")):
            error = museum.switch(self.config)
            self.assertIn("Could not reach Wikimedia", error)
            state = museum.read_json(self.state / "state.json")
            self.assertEqual(state["errorKind"], "network")
            self.assertLess(time.time() - state["setAt"], 5)
            self.assertFalse(museum.is_due(museum.normalize_config({})))
            museum.switch(self.config)
        self.assertEqual(len(self.platform.notifications), 1)

    def test_failing_background_setter_is_recorded(self):
        queue = self.cache / "queue"
        queue.mkdir()
        (queue / "commons-1.jpg").write_bytes(b"jpg")
        museum.write_json(queue / "commons-1.json", {"title": "T", "filter": museum.queue_key(self.config)})
        with mock.patch.object(museum, "set_background", side_effect=OSError("access denied")):
            error = museum.switch(self.config)
        self.assertIn("Could not set the background", error)
        self.assertEqual(museum.read_json(self.state / "state.json")["errorKind"], "background")

    def test_symlinked_paths_still_count_as_ours(self):
        saved = Path(os.path.realpath(self.tmp.name)) / "saved"
        saved.mkdir()
        (saved / "hay.jpg").write_bytes(b"jpg")
        alias = Path(self.tmp.name) / "alias"
        try:
            alias.symlink_to(saved, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks need extra rights on this system")
        museum.record(alias / "hay.jpg")
        self.set_link(saved / "hay.jpg")
        self.assertTrue(museum.status(self.config)["active"])
        self.assertFalse(museum.status(self.config)["fromCache"])

    def test_small_pool_repeats_instead_of_failing(self):
        (self.cache / "commons-7.jpg").write_bytes(b"jpg")
        page = {"pageid": 7, "title": "File:X.jpg", "imageinfo": [{"width": 4000, "height": 2500}]}
        filters = museum.normalize_filters({"artists": ["Q296"]})
        with mock.patch.object(museum, "active_filters", return_value=filters), \
             mock.patch.object(museum, "filtered_candidates", return_value=[(page, "Q1")]), \
             mock.patch.object(museum, "entity_pool", return_value=[["Q1", "File:X.jpg"]]), \
             mock.patch.object(museum, "enqueue", return_value=self.cache / "queue" / "commons-7.jpg") as enqueue:
            self.assertEqual(museum.fetch_next(self.config).name, "commons-7.jpg")
        enqueue.assert_called_once()

    def test_single_match_already_showing_keeps_it_quietly(self):
        current = self.cache / "commons-7.jpg"
        current.write_bytes(b"jpg")
        self.set_link(current)
        page = {"pageid": 7, "title": "File:X.jpg", "imageinfo": [{"width": 4000, "height": 2500}]}
        filters = museum.normalize_filters({"artists": ["Q296"]})
        with mock.patch.object(museum, "active_filters", return_value=filters), \
             mock.patch.object(museum, "filtered_candidates", return_value=[(page, "Q1")]), \
             mock.patch.object(museum, "entity_pool", return_value=[["Q1", "File:X.jpg"]]), \
             mock.patch.object(museum, "set_background") as set_background:
            self.assertEqual(museum.switch(self.config), "")
        set_background.assert_not_called()
        self.assertEqual(museum.read_json(self.state / "state.json")["errorKind"], "")

    def test_offline_fallback_cycles_downloaded_paintings(self):
        for name in ("commons-1.jpg", "commons-2.jpg"):
            (self.cache / name).write_bytes(b"jpg")
        self.set_link(self.cache / "commons-1.jpg")
        with mock.patch.object(museum, "fetch_next", side_effect=OSError("offline")), \
             mock.patch.object(museum, "set_background") as set_background:
            museum.switch(self.config)
        set_background.assert_called_once_with({"m1": self.cache / "commons-2.jpg"})

    def queue_image(self, name, key, age):
        queue = self.cache / "queue"
        queue.mkdir(exist_ok=True)
        image = queue / f"{name}.jpg"
        museum.write_json(image.with_suffix(".json"), {"title": name, "filter": key})
        image.write_bytes(b"jpg")
        os.utime(image, (age, age))
        return image

    def test_queue_serves_oldest_and_drops_stale(self):
        key = museum.queue_key(self.config)
        newer = self.queue_image("commons-2", key, 2000)
        older = self.queue_image("commons-1", key, 1000)
        stale = self.queue_image("commons-3", "other-filter", 500)
        self.assertEqual(museum.queue_items(self.config), [older, newer])
        self.assertEqual(museum.queued(self.config), older)
        self.assertFalse(stale.exists())

    def test_prefetch_fills_the_queue_to_count(self):
        key = museum.queue_key(self.config)
        made = []

        def fake_fetch(_config):
            made.append(self.queue_image(f"commons-{len(made) + 1}", key, 1000 + len(made)))
            return made[-1]

        lock = threading.Lock()

        def fake_fetch_locked(config):
            with lock:
                return fake_fetch(config)

        with mock.patch.object(museum, "fetch_next", side_effect=fake_fetch_locked):
            museum.prefetch(self.config)
        self.assertEqual(len(museum.queue_items(self.config)), self.config["prefetchCount"])
        self.assertEqual(len(made), self.config["prefetchCount"])

    def test_second_prefetcher_backs_off(self):
        first = museum.lock(".prefetcher.lock", wait=False)
        try:
            self.assertIsNotNone(first)
            self.assertIsNone(museum.lock(".prefetcher.lock", wait=False))
        finally:
            first.close()

    def small_pool(self, *ids):
        pages = [({"pageid": i, "title": f"File:{i}.jpg", "imageinfo": [{"width": 4000, "height": 2500}]}, f"Q{i}")
                 for i in ids]
        filters = museum.normalize_filters({"artists": ["Q296"]})
        return [mock.patch.object(museum, "active_filters", return_value=filters),
                mock.patch.object(museum, "filtered_candidates", return_value=pages),
                mock.patch.object(museum, "entity_pool", return_value=[[q, p["title"]] for p, q in pages])]

    def test_queued_paintings_are_not_fetched_again(self):
        (self.cache / "commons-8.jpg").write_bytes(b"jpg")
        self.set_link(self.cache / "commons-8.jpg")
        self.queue_image("commons-7", "any", 1000)
        patches = self.small_pool(7, 8)
        for patch in patches:
            patch.start()
        with mock.patch.object(museum, "enqueue") as enqueue:
            with self.assertRaises(museum.AllQueued):
                museum.fetch_next(self.config)
            museum.prefetch(self.config)
        enqueue.assert_not_called()

    def test_a_download_in_flight_claims_its_painting(self):
        queue = self.cache / "queue"
        queue.mkdir()
        museum.write_json(queue / "commons-7.json", {"title": "in flight"})
        for patch in self.small_pool(7):
            patch.start()
        with mock.patch.object(museum, "enqueue") as enqueue, self.assertRaises(museum.AllQueued):
            museum.fetch_next(self.config)
        enqueue.assert_not_called()

    def test_orphan_sidecars_are_cleaned(self):
        queue = self.cache / "queue"
        queue.mkdir()
        orphan = queue / "commons-9.json"
        museum.write_json(orphan, {"title": "killed"})
        os.utime(orphan, (1000, 1000))
        fresh = queue / "commons-10.json"
        museum.write_json(fresh, {"title": "downloading"})
        museum.queued(self.config)
        self.assertFalse(orphan.exists())
        self.assertTrue(fresh.exists())

    def test_prefetch_falls_back_to_random_and_backs_off_on_failure(self):
        calls = []

        def fetch(_config, unfiltered=False, note=None):
            calls.append(unfiltered)
            if not unfiltered:
                raise museum.NoMatch("nothing")
            raise OSError("offline")

        with mock.patch.object(museum, "fetch_next", side_effect=fetch):
            museum.prefetch(self.config)
        # Each parallel download tried the filter, then a random painting, then gave up.
        self.assertEqual(sorted(calls), [False] * museum.PREFETCH_WORKERS + [True] * museum.PREFETCH_WORKERS)
        self.assertFalse(museum.prefetch_wanted(self.config))
        museum.write_json(self.cache / ".prefetch-failed.json", {"at": time.time() - 3600, "filter": "x"})
        self.assertTrue(museum.prefetch_wanted(self.config))

    def test_small_pool_prefetch_backs_off(self):
        with mock.patch.object(museum, "fetch_next", side_effect=museum.AllQueued("all queued")):
            museum.prefetch(self.config)
        self.assertFalse(museum.prefetch_wanted(self.config))

    def test_queued_random_painting_still_reports_the_filter(self):
        key = museum.queue_key(self.config)
        image = self.queue_image("commons-99", key, 1000)
        museum.write_json(image.with_suffix(".json"), {"title": "R", "filter": key, "filterError": "nothing matches"})
        with mock.patch.object(museum, "set_background"):
            error = museum.switch(self.config)
        self.assertIn("nothing matches", error)
        self.assertEqual(museum.read_json(self.state / "state.json")["errorKind"], "filter")

    def test_failure_is_stamped_for_the_filter_it_happened_under(self):
        def fetch(_config, unfiltered=False, note=None):
            museum.write_json(self.state / "filter.json", {"artists": [{"id": "Q296", "label": "Monet"}]})
            raise OSError("queue wiped")

        old_key = museum.queue_key(self.config)
        with mock.patch.object(museum, "fetch_next", side_effect=fetch):
            museum.prefetch(self.config)
        self.assertEqual(museum.read_json(self.cache / ".prefetch-failed.json")["filter"], old_key)
        self.assertTrue(museum.prefetch_wanted(self.config))

    def test_language_change_retires_the_queue(self):
        image = self.queue_image("commons-5", museum.queue_key(self.config), 1000)
        german = museum.normalize_config({"saveDir": self.config["saveDir"], "language": "de"})
        self.assertEqual(museum.queue_items(self.config), [image])
        self.assertEqual(museum.queue_items(german), [])

    def test_fit_modes(self):
        painting = make_jpeg(self.cache / "commons-5.jpg")
        cover = museum.normalize_config({"fit": "cover", "caption": "off"})
        self.assertEqual(museum.render(painting, cover), painting)
        blurred = museum.render(painting, museum.normalize_config({"fit": "blur", "caption": "off"}))
        self.assertEqual(blurred, self.cache / "display" / "commons-5.blur.none.384x216.0.jpg")
        self.assertEqual(museum.image_size(blurred), (384, 216))
        wall = museum.render(painting, museum.normalize_config({"fit": "wall", "caption": "off"}))
        self.assertEqual(wall.name, "commons-5.wall.none.384x216.0.jpg")
        from PIL import Image
        with Image.open(wall) as image:
            self.assertEqual(image.getpixel((1, 1)), museum.WALL_COLOR)
        self.assertEqual(list((self.cache / "display").glob("*.part")), [])

    def test_auto_fit_frames_only_heavy_crops(self):
        painting = make_jpeg(self.cache / "commons-5.jpg")
        auto = museum.normalize_config({"fit": "auto", "caption": "off"})
        with mock.patch.object(museum, "image_size", return_value=(3840, 2200)):
            self.assertEqual(museum.render(painting, auto), painting)
        with mock.patch.object(museum, "image_size", return_value=(3840, 2925)):
            self.assertEqual(museum.render(painting, auto).name, "commons-5.auto.none.384x216.0.jpg")

    def test_broken_image_shows_the_original(self):
        painting = self.cache / "commons-5.jpg"
        painting.write_bytes(b"not a jpeg")
        self.assertEqual(museum.render(painting, museum.normalize_config({"caption": "off"})), painting)

    def test_caption_is_drawn_even_when_filling(self):
        painting = make_jpeg(self.cache / "commons-5.jpg", size=(384, 216))
        museum.write_json(painting.with_suffix(".json"), {"title": "The Ninth Wave", "artist": "Ivan Aivazovsky",
                                                          "year": "1850", "museum": "Russian Museum"})
        config = museum.normalize_config({"fit": "cover", "caption": "bottom-right"})
        shown = museum.render(painting, config)
        self.assertEqual(shown.name, "commons-5.cover.bottom-right.384x216.0-0-0-12.jpg")
        from PIL import Image
        with Image.open(shown) as image, Image.open(painting) as original:
            # The label sits in the bottom right corner, above the taskbar inset.
            self.assertNotEqual(image.getpixel((370, 190)), original.getpixel((370, 190)))
            self.assertLess(sum(abs(a - b) for a, b in zip(image.getpixel((10, 10)), original.getpixel((10, 10)))), 20)

    def test_every_monitor_gets_its_own_size_once(self):
        self.platform._monitors = [Monitor("a", 384, 216), Monitor("b", 216, 384), Monitor("c", 384, 216)]
        painting = make_jpeg(self.cache / "commons-5.jpg")
        config = museum.normalize_config({"fit": "blur", "caption": "off"})
        shown = museum.show(painting, config)
        wall = self.platform.walls[-1]
        self.assertEqual(set(wall), {"a", "b", "c"})
        self.assertEqual(wall["a"], wall["c"])
        self.assertNotEqual(wall["a"], wall["b"])
        self.assertEqual(museum.image_size(wall["b"]), (216, 384))
        self.assertEqual(shown, wall["a"])

    def test_prune_keeps_the_copies_for_every_monitor(self):
        painting = make_jpeg(self.cache / "commons-5.jpg")
        self.platform._monitors = [Monitor("a", 384, 216), Monitor("b", 216, 384)]
        config = museum.normalize_config({"fit": "blur", "caption": "off", "saveDir": self.config["saveDir"]})
        museum.record(museum.show(painting, config), original=painting, config=config)
        old = self.cache / "display" / "commons-4.blur.none.384x216.0.jpg"
        old.write_bytes(b"old")
        museum.prune(config)
        self.assertEqual(len(list((self.cache / "display").glob("commons-5.*.jpg"))), 2)
        self.assertFalse(old.exists())

    def test_monitor_change_reframes(self):
        painting = make_jpeg(self.cache / "commons-5.jpg")
        config = museum.normalize_config({"fit": "blur", "caption": "off", "saveDir": self.config["saveDir"]})
        museum.record(museum.show(painting, config), original=painting, config=config)
        museum.refit(config)
        self.assertEqual(len(self.platform.walls), 1)
        self.platform._monitors = [Monitor("m1", 384, 216), Monitor("m2", 300, 200)]
        museum.refit(config)
        self.assertEqual(set(self.platform.walls[-1]), {"m1", "m2"})
        museum.refit(config)
        self.assertEqual(len(self.platform.walls), 2)

    def test_status_describes_the_painting_behind_a_framed_copy(self):
        painting = self.cache / "commons-5.jpg"
        painting.write_bytes(b"jpg")
        museum.write_json(painting.with_suffix(".json"), {"title": "The Ninth Wave"})
        framed = self.cache / "display" / "commons-5.blur.jpg"
        framed.parent.mkdir()
        framed.write_bytes(b"framed")
        stale = self.cache / "display" / "commons-4.blur.jpg"
        stale.write_bytes(b"old")
        self.set_link(framed)
        museum.record(framed, original=painting)
        current = museum.status(self.config)
        self.assertTrue(current["active"])
        self.assertTrue(current["fromCache"])
        self.assertEqual(current["image"], str(painting))
        self.assertEqual(current["info"]["title"], "The Ninth Wave")
        museum.prune(self.config)
        self.assertTrue(framed.exists())
        self.assertFalse(stale.exists())

    def test_changed_fit_reframes_without_restarting_the_interval(self):
        painting = make_jpeg(self.cache / "commons-5.jpg")
        self.set_link(painting)
        museum.record(painting, original=painting)  # as before `fit` existed
        set_at = museum.read_json(self.state / "state.json")["setAt"] - 100
        museum.write_json(self.state / "state.json", {**museum.read_json(self.state / "state.json"), "setAt": set_at})
        blur = museum.normalize_config({"fit": "blur", "caption": "off"})
        with mock.patch.object(museum, "set_background", wraps=museum.set_background) as set_background:
            museum.refit(blur)
            museum.refit(blur)
        set_background.assert_called_once_with({"m1": self.cache / "display" / "commons-5.blur.none.384x216.0.jpg"})
        state = museum.read_json(self.state / "state.json")
        self.assertEqual((state["fit"], state["setAt"]), ("blur", set_at))

    def test_caption_change_reframes(self):
        painting = make_jpeg(self.cache / "commons-5.jpg")
        museum.write_json(painting.with_suffix(".json"), {"title": "Poppies", "artist": "Claude Monet"})
        config = museum.normalize_config({"fit": "blur", "caption": "off", "saveDir": self.config["saveDir"]})
        museum.record(museum.show(painting, config), original=painting, config=config)
        museum.refit(museum.normalize_config({**config, "caption": "top-left"}))
        self.assertIn(".top-left.", self.platform.walls[-1]["m1"].name)
        self.assertEqual(museum.read_json(self.state / "state.json")["caption"], "top-left")

    def test_a_theme_background_is_never_claimed(self):
        theme = Path(self.tmp.name) / "theme-forest.jpg"
        theme.write_bytes(b"jpg")
        self.set_link(theme)
        with mock.patch.object(museum, "fetch_next", side_effect=OSError("offline")), \
             mock.patch.object(museum, "set_background") as set_background:
            museum.switch(self.config)
            museum.refit(museum.normalize_config({"saveDir": self.config["saveDir"], "fit": "blur"}))
        set_background.assert_not_called()
        self.assertFalse(museum.status(self.config)["active"])

    def test_saving_twice_keeps_one_copy(self):
        painting = self.cache / "commons-5.jpg"
        painting.write_bytes(b"jpg")
        museum.write_json(painting.with_suffix(".json"), {"id": "Q1", "title": "Poppies", "artist": "Claude Monet"})
        self.set_link(painting)
        museum.cmd_keep(self.config, None)
        museum.cmd_keep(self.config, None)
        saved = Path(self.config["saveDir"])
        self.assertEqual(sorted(p.name for p in saved.glob("*.jpg")), ["claude-monet-poppies.jpg"])
        self.assertEqual(list(museum.saved_index(self.config)), ["claude-monet-poppies.jpg"])
        self.assertEqual([n[0] for n in self.platform.notifications],
                         ["Saved to your collection", "Already in your collection"])

    def test_cyrillic_credits_survive(self):
        painting = self.cache / "commons-6.jpg"
        painting.write_bytes(b"jpg")
        museum.write_json(painting.with_suffix(".json"), {"id": "Q2", "title": "Девятый вал", "artist": "Иван Айвазовский"})
        self.set_link(painting)
        museum.cmd_keep(self.config, None)
        saved = Path(self.config["saveDir"])
        self.assertEqual([p.name for p in saved.glob("*.jpg")], ["иван-айвазовский-девятый-вал.jpg"])
        self.assertEqual(museum.local_credit(saved / "иван-айвазовский-девятый-вал.jpg"), "Иван Айвазовский, Девятый вал")

    def test_notification_has_a_read_more_button_that_opens_the_article(self):
        painting = self.cache / "commons-6.jpg"
        painting.write_bytes(b"jpg")
        museum.write_json(painting.with_suffix(".json"), {"title": "Poppies", "artist": "Claude Monet", "year": "1873",
                                                          "url": "https://en.wikipedia.org/wiki/Poppies"})
        self.set_link(painting)
        museum.record(painting)
        museum.cmd_notify(self.config, None)
        title, body, buttons = self.platform.notifications[-1]
        self.assertEqual((title, buttons), ("Poppies", ["Read more"]))
        self.assertIn("Claude Monet · 1873", body)
        museum.cmd_open(self.config, None)
        self.assertEqual(self.platform.opened, ["https://en.wikipedia.org/wiki/Poppies"])

    # ---- 0.1.2: parallel prefetch, waiting for downloads, framing ahead

    def test_parallel_claims_take_each_painting_once(self):
        key = museum.queue_key(self.config)
        results = []
        barrier = threading.Barrier(8)

        def worker():
            barrier.wait()
            results.append(museum.claim("commons-42", key))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(results), ["claimed"] + ["queued"] * 7)
        self.assertEqual(museum.in_flight(key), 1)

    def test_shown_paintings_are_not_claimed_unless_repeating(self):
        key = museum.queue_key(self.config)
        (self.cache / "commons-7.jpg").write_bytes(b"jpg")
        self.assertEqual(museum.claim("commons-7", key), "shown")
        self.assertEqual(museum.claim("commons-7", key, allow_shown=True), "claimed")

    def test_stale_claims_from_other_processes_do_not_count(self):
        key = museum.queue_key(self.config)
        queue = self.cache / "queue"
        queue.mkdir()
        sidecar = queue / "commons-9.json"
        museum.write_json(sidecar, {"filter": key, "claimedBy": -1})
        self.assertEqual(museum.in_flight(key), 1)
        old = time.time() - museum.IN_FLIGHT_AGE - 5
        os.utime(sidecar, (old, old))
        self.assertEqual(museum.in_flight(key), 0)
        museum.write_json(sidecar, {"filter": key, "claimedBy": os.getpid()})
        os.utime(sidecar, (old, old))
        self.assertEqual(museum.in_flight(key), 1)

    def test_switch_waits_for_a_download_in_flight(self):
        key = museum.queue_key(self.config)
        museum.claim("commons-11", key)

        def finish():
            time.sleep(0.4)
            self.queue_image("commons-11", key, time.time())

        threading.Thread(target=finish).start()
        with mock.patch.object(museum, "fetch_next") as fetch, mock.patch.object(museum, "set_background"):
            self.assertEqual(museum.switch(self.config), "")
        fetch.assert_not_called()
        self.assertTrue((self.cache / "commons-11.jpg").exists())

    def test_thumbnail_widths_are_standard_steps(self):
        self.assertEqual(museum.thumb_width(3840), 3840)
        self.assertEqual(museum.thumb_width(2560), 3840)
        self.assertEqual(museum.thumb_width(1920), 1920)
        self.assertEqual(museum.thumb_width(2000), 1920)  # 0.95 of the screen is sharp enough
        self.assertEqual(museum.thumb_width(1366), 1920)
        self.assertEqual(museum.thumb_width(1280), 1280)
        self.assertEqual(museum.thumb_width(5120), 3840)
        for width in (800, 1366, 1600, 2560, 3440, 3840, 7680):
            self.assertIn(museum.thumb_width(width), museum.THUMB_STEPS)
        # Height counts too: a 2:1 painting must cover a 5:4 screen's height.
        self.assertEqual(museum.thumb_width((1280, 1024), 2.0), 3840)  # needs 2048 px
        self.assertEqual(museum.thumb_width((1280, 1024), 1.3), 1280)
        self.assertEqual(museum.thumb_width((1920, 1080), 1.5), 1920)
        self.assertEqual(museum.thumb_width((3840, 2160), 2.0), 3840)

    def test_thumbnail_covers_every_monitor(self):
        page = {"imageinfo": [{"width": 6000, "height": 4000}]}  # 3:2
        self.platform._monitors = [Monitor("wide", 1920, 1080, (0, 0, 0, 0))]
        self.assertEqual(museum.thumb_width_for(page), 1920)
        # A portrait monitor beside it: 1920 px high needs 2880 px of a 3:2 painting.
        self.platform._monitors.append(Monitor("tall", 1080, 1920, (0, 0, 0, 0)))
        self.assertEqual(museum.thumb_width_for(page), 3840)

    def test_language_preference_orders_or_narrows_candidates(self):
        found = [({"pageid": 1}, "Q1"), ({"pageid": 2}, "Q2"), ({"pageid": 3}, "Q3")]
        answer = {"Q1": {"labels": {}, "sitelinks": {}},
                  "Q2": {"labels": {"ru": {"value": "Девятый вал"}}, "sitelinks": {}},
                  "Q3": {"labels": {"ru": {"value": "Гадалка"}}, "sitelinks": {"ruwiki": {"title": "Гадалка"}}}}
        prefer = museum.normalize_config({"language": "ru", "localized": "prefer"})
        only = museum.normalize_config({"language": "ru", "localized": "only"})
        by_article = museum.normalize_config({"language": "ru", "localized": "only", "localizedBy": "article"})
        with mock.patch.object(museum, "entities", return_value=answer) as asked:
            self.assertEqual([q for _, q in museum.prefer_described(found, prefer)], ["Q2", "Q3", "Q1"])
            self.assertEqual([q for _, q in museum.prefer_described(found, only)], ["Q2", "Q3"])
            self.assertEqual([q for _, q in museum.prefer_described(found, by_article)], ["Q3"])
        self.assertEqual(asked.call_args.kwargs, {"props": "labels|sitelinks", "languages": "ru", "site": "ruwiki"})
        everyone = museum.normalize_config({"localized": "all"})
        self.assertEqual(museum.prefer_described(found, everyone), found)
        with mock.patch.object(museum, "entities", side_effect=OSError("offline")), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(museum.prefer_described(found, only), found)  # no answer: no preference

    def test_language_preference_settings(self):
        config = museum.normalize_config({})
        self.assertEqual((config["localized"], config["localizedBy"]), ("prefer", "title"))
        odd = museum.normalize_config({"localized": "never", "localizedBy": 3})
        self.assertEqual((odd["localized"], odd["localizedBy"]), ("prefer", "title"))
        self.assertNotEqual(museum.queue_key(museum.normalize_config({"localized": "only"})),
                            museum.queue_key(museum.normalize_config({"localized": "all"})))
        # "prefer" and "all" may queue the same paintings.
        self.assertEqual(museum.queue_key(museum.normalize_config({"localized": "prefer"})),
                         museum.queue_key(museum.normalize_config({"localized": "all"})))

    def test_unknown_wiki_means_no_answer(self):
        config = museum.normalize_config({"language": "nb", "localized": "only", "localizedBy": "article"})
        unfiltered = {"Q1": {"sitelinks": {"enwiki": {}, "nowiki": {}}}}  # sitefilter ignored
        with mock.patch.object(museum, "entities", return_value=unfiltered):
            self.assertIsNone(museum.described_in({"Q1"}, config))
        with mock.patch.object(museum, "entities", return_value={}):
            self.assertIsNone(museum.described_in({"Q1"}, config))

    def test_english_titles_need_no_check(self):
        found = [({"pageid": 1}, "Q1")]
        with mock.patch.object(museum, "described_in", side_effect=AssertionError("asked")):
            self.assertEqual(museum.prefer_described(found, museum.normalize_config({"language": "en"})), found)

    def test_only_blames_the_language_only_when_it_dropped_something(self):
        page = {"pageid": 7, "title": "File:X.jpg", "imageinfo": [{"width": 4000, "height": 2500}]}
        only = museum.normalize_config({"saveDir": self.config["saveDir"], "fit": "cover", "fame": "any",
                                        "language": "ru", "localized": "only"})
        filters = museum.normalize_filters({"artists": ["Q296"]})
        with mock.patch.object(museum, "active_filters", return_value=filters), \
             mock.patch.object(museum, "resolve_filters", return_value=(filters, [])), \
             mock.patch.object(museum, "entity_pool", return_value=[["Q1", "File:X.jpg"]]):
            with mock.patch.object(museum, "filtered_candidates", return_value=[(page, "Q1")]), \
                 mock.patch.object(museum, "described_in", return_value=set()):
                with self.assertRaises(museum.NoMatch) as caught:
                    museum.fetch_next(only)
                self.assertEqual(str(caught.exception), strings.t("nm_localized", "ru"))
            with mock.patch.object(museum, "filtered_candidates", return_value=[]):
                with self.assertRaises(museum.NoMatch) as caught:
                    museum.fetch_next(only)
                self.assertEqual(str(caught.exception), strings.t("nm_too_small", "ru"))

    def test_the_fallback_relaxes_only(self):
        page = {"pageid": 7, "title": "File:X.jpg", "imageinfo": [{"width": 4000, "height": 2500}]}
        only = museum.normalize_config({"saveDir": self.config["saveDir"], "fit": "cover", "fame": "any",
                                        "language": "ru", "localized": "only"})
        with mock.patch.object(museum, "random_candidates", return_value=[(page, "Q1")]), \
             mock.patch.object(museum, "described_in", return_value=set()), \
             mock.patch.object(museum, "enqueue", return_value=self.cache / "queue" / "commons-7.jpg") as enqueue:
            museum.fetch_next(only, unfiltered=True)
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.args[3], museum.queue_key(only))  # still lands in the "only" queue

    def test_stories_are_longer(self):
        text = " ".join(f"Sentence number {n} is here." for n in range(1, 10))
        with mock.patch.object(museum, "http_json", return_value={"extract": text, "content_urls": {}}):
            summary, _ = museum.wikipedia_summary("en", "X")
        self.assertTrue(summary.endswith("number 6 is here."))
        self.assertLessEqual(len(museum.commons_description("word " * 400)), 601)

    def test_candidates_are_checked_without_extmetadata(self):
        answer = {"query": {"pages": [{"title": "File:A.jpg", "pageid": 1,
                                       "imageinfo": [{"width": 4000, "height": 2500}]}]}}
        with mock.patch.object(museum, "mw_api", return_value=answer) as api:
            museum.image_infos(["File:A.jpg"])
        self.assertEqual(api.call_args.kwargs["iiprop"], "size|url")
        self.assertNotIn("iiextmetadatafilter", api.call_args.kwargs)

    def test_describe_fetches_metadata_for_the_picked_painting_only(self):
        page = {"pageid": 7, "title": "File:X.jpg",
                "imageinfo": [{"width": 4000, "height": 2500, "descriptionurl": "https://commons.example/X"}]}
        meta = {"ObjectName": {"value": "The\u200b Wave"}}
        with mock.patch.object(museum, "file_metadata", return_value=meta) as file_metadata, \
             mock.patch.object(museum, "entities", return_value={}), \
             mock.patch.object(museum, "http_json", side_effect=OSError("offline")):
            info = museum.describe(page, "Q1", "en")
        file_metadata.assert_called_once_with(7)
        self.assertEqual(info["title"], "The Wave")  # invisible characters dropped

    def test_one_pool_query_for_concurrent_callers(self):
        filters = museum.normalize_filters({"artists": ["Q296"]})
        path = self.cache / "pools" / "test.json"
        started = threading.Barrier(3)
        calls = []

        def slow_query(_filters):
            calls.append(1)
            time.sleep(0.2)
            return [["Q1", "File:A.jpg"]]

        def load():
            started.wait()
            return museum._load_pool(path, filters)

        with mock.patch.object(museum, "query_pool", side_effect=slow_query):
            threads = [threading.Thread(target=load) for _ in range(3)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        self.assertEqual(len(calls), 1)

    def test_claims_of_dead_processes_are_not_waited_for(self):
        queue = self.cache / "queue"
        queue.mkdir(exist_ok=True)
        key = museum.queue_key(self.config)
        museum.write_json(queue / "commons-8.json", {"filter": key, "claimedBy": 999999999})
        with mock.patch.object(self.platform, "process_alive", return_value=False):
            self.assertEqual(museum.in_flight(key), 0)
        with mock.patch.object(self.platform, "process_alive", return_value=True):
            self.assertEqual(museum.in_flight(key), 1)
        self.assertTrue(museum.alive(os.getpid()))
        self.assertTrue(museum.alive(None))  # unknown counts as running

    def test_a_dead_claim_frees_its_painting_at_once(self):
        queue = self.cache / "queue"
        queue.mkdir(exist_ok=True)
        claim = queue / "commons-9.json"
        museum.write_json(claim, {"filter": "k", "claimedBy": 999999999})
        with mock.patch.object(self.platform, "process_alive", return_value=True):
            museum.queued(self.config)
        self.assertTrue(claim.exists())
        with mock.patch.object(self.platform, "process_alive", return_value=False):
            museum.queued(self.config)
        self.assertFalse(claim.exists())

    def test_queued_paintings_are_framed_ahead_and_kept(self):
        key = museum.queue_key(self.config)
        config = museum.normalize_config({**self.config, "fit": "blur", "caption": "bottom-right"})
        key = museum.queue_key(config)
        image = make_jpeg(self.cache / "queue" / "commons-21.jpg")
        museum.write_json(image.with_suffix(".json"), {"title": "Poppies", "artist": "Claude Monet", "filter": key})
        museum.prerender(image, config)
        framed = list((self.cache / "display").glob("commons-21.*.jpg"))
        self.assertEqual(len(framed), 1)
        museum.prune(config)
        self.assertTrue(framed[0].exists())
        with mock.patch.object(museum.framing, "frame") as frame:
            museum.switch(config)
        frame.assert_not_called()
        self.assertEqual(self.platform.walls[-1]["m1"], framed[0])

    def test_queued_paintings_are_described_by_their_sidecar(self):
        image = self.queue_image("commons-22", "k", 1000)
        museum.write_json(image.with_suffix(".json"), {"title": "The Hay Wain", "filter": "k"})
        self.assertEqual(museum.info_for(image, self.config)["title"], "The Hay Wain")

    def test_describe_fetches_in_parallel_and_falls_back(self):
        page = {"title": "File:X.jpg", "imageinfo": [{"descriptionurl": "https://commons/X",
                                                      "extmetadata": {}}]}
        painting = {"labels": {"en": {"value": "Poppies"}}, "sitelinks": {"enwiki": {"title": "Poppies"}},
                    "claims": {**claim("P170", {"id": "Q296"}), **claim("P135", {"id": "Q40415"})}}
        artist = {"labels": {"en": {"value": "Claude Monet"}}, "sitelinks": {"enwiki": {"title": "Claude Monet"}}}

        def entities(ids, **_kwargs):
            data = {"Q1": painting, "Q296": artist, "Q40415": {"labels": {"en": {"value": "Impressionism"}}}}
            return {i: data[i] for i in ids if i in data}

        threads = set()

        def summary(language, title):
            threads.add(threading.current_thread().name)
            return ("", None) if title == "Poppies" else (f"{title} was a painter.", f"https://en/{title}")

        with mock.patch.object(museum, "entities", side_effect=entities), \
                mock.patch.object(museum, "wikipedia_summary", side_effect=summary):
            info = museum.describe(page, "Q1", "en")
        self.assertEqual((info["title"], info["artist"], info["movement"]), ("Poppies", "Claude Monet", "Impressionism"))
        self.assertEqual(info["summary"], "About the artist: Claude Monet was a painter.")
        self.assertEqual(info["url"], "https://en/Claude Monet")
        self.assertTrue(any(name.startswith("describe") for name in threads))

    def test_filter_change_leaves_downloads_alone(self):
        queue = self.cache / "queue"
        queue.mkdir()
        part = queue / "commons-7.jpg.123.part"
        part.write_bytes(b"half")
        args = mock.Mock(action="clear", switch=False)
        with contextlib.redirect_stdout(io.StringIO()):
            museum.cmd_filter(self.config, args)
        self.assertTrue(part.exists())


if __name__ == "__main__":
    unittest.main()
