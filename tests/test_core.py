"""Pure-Python tests (no Qt, no network). Run:  python -m unittest discover -s tests -v"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from lyricpip.lyrics.lrc import parse_lrc, parse_plain
from lyricpip.lyrics.matching import best_match
from lyricpip.models import PlaybackState, TrackInfo
from lyricpip.romanize import detect_song_language, needs_romanization
from lyricpip.textutil import clean_title, query_variants


class LrcTests(unittest.TestCase):
    def test_basic_and_multi_stamp(self):
        lines = parse_lrc("[ar:X]\n[00:01.50] hello\n[00:10.00][00:50.5] chorus\n")
        self.assertEqual(
            [(l.time, l.text) for l in lines],
            [(1.5, "hello"), (10.0, "chorus"), (50.5, "chorus")],
        )

    def test_offset_and_word_tags(self):
        lines = parse_lrc("[offset:500]\n[00:02.00]<00:02.00>hi <00:02.40>there")
        self.assertEqual((lines[0].time, lines[0].text), (1.5, "hi there"))

    def test_plain(self):
        self.assertEqual([l.text for l in parse_plain("a\r\nb")], ["a", "b"])


class TextTests(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(clean_title("Song (Official Video) [4K] feat. Bob"), "Song")

    def test_variants_split_artist_title(self):
        v = query_variants(
            TrackInfo("Queen - Bohemian Rhapsody (Official Video)", "QueenVEVO")
        )
        self.assertIn(("Queen", "Bohemian Rhapsody"), [(t.artist, t.title) for t in v])


class SuffixNoiseTests(unittest.TestCase):
    def test_suffix_forms_are_removed(self):
        for raw in [
            "Talkin 2 Myself (Official Animated Music Video)",
            "Talkin 2 Myself | Animated Music Video",
            "Talkin 2 Myself - Official Music Video",
            "Talkin 2 Myself Official Music Video",
            "【MV】Talkin 2 Myself",
            "Talkin 2 Myself [4K] (Official Video)",
        ]:
            self.assertEqual(clean_title(raw), "Talkin 2 Myself", raw)

    def test_real_titles_containing_noise_words_survive(self):
        for t in [
            "Video Games",
            "Home Video",
            "Music Video Killed Me",
            "Live at Wembley",
        ]:
            self.assertEqual(clean_title(t), t)
        self.assertEqual(
            clean_title("Song (Live at Wembley)"), "Song (Live at Wembley)"
        )

    def test_artist_field_decides_which_segment_is_the_title(self):
        v = query_variants(
            TrackInfo(
                "Eminem - Talkin 2 Myself (Official Animated Music Video)", "EminemVEVO"
            )
        )
        self.assertEqual((v[0].artist, v[0].title), ("Eminem", "Talkin 2 Myself"))

    def test_channel_title_only(self):
        v = query_variants(
            TrackInfo("Talkin 2 Myself | Animated Music Video", "Some Channel")
        )
        self.assertEqual(v[0].title, "Talkin 2 Myself")

    def test_quoted_title_variant(self):
        v = query_variants(
            TrackInfo('Eminem "Lose Yourself" (Official Video)', "Eminem")
        )
        self.assertIn("Lose Yourself", [t.title for t in v])

    def test_never_returns_empty(self):
        self.assertTrue(clean_title("Official Video"))


@unittest.skipUnless(
    __import__("importlib").util.find_spec("requests")
    and __import__("importlib").util.find_spec("platformdirs"),
    "needs requests + platformdirs",
)
class ManualSearchTests(unittest.TestCase):
    def test_manual_query_is_cached_under_playing_song(self):
        import tempfile

        from lyricpip.config import Config
        from lyricpip.lyrics.manager import LyricsManager
        from lyricpip.lyrics.providers.base import Provider
        from lyricpip.models import RawLyrics

        class Fake(Provider):
            name = "fake"

            def fetch(self, t):
                return (
                    RawLyrics("fake", lrc="[00:01.00]a\n[00:02.00]b")
                    if t.title == "Right Title"
                    else None
                )

        cfg = Config()
        cfg.providers = []
        m = LyricsManager(cfg)
        m.providers = [Fake(cfg)]
        m.cache.dir = pathlib.Path(tempfile.mkdtemp())
        playing = TrackInfo("Messy Video Title", "Some Channel", duration=200)

        self.assertIsNone(m.get(playing))  # automatic: miss
        res = m.get(
            TrackInfo("Right Title", "", duration=200),
            cache_key=playing.key,
            use_cache=False,
        )  # manual: hit
        self.assertTrue(res and res.synced)
        self.assertIsNotNone(m.cache.load(playing.key))  # stored for the playing song
        self.assertTrue(m.get(playing).synced)  # next automatic lookup reuses it

    def test_title_only_query_scores(self):
        from lyricpip.lyrics.matching import score

        self.assertGreater(
            score(TrackInfo("Right Title", ""), "Right Title", "Whoever", None), 0.9
        )


class MatchTests(unittest.TestCase):
    def test_duration_breaks_tie(self):
        t = TrackInfo("Yesterday", "The Beatles", duration=125)
        pick = best_match(
            t,
            [
                ("live", "Yesterday", "The Beatles", 200),
                ("studio", "Yesterday", "The Beatles", 126),
            ],
        )
        self.assertEqual(pick, "studio")


class MiscTests(unittest.TestCase):
    def test_script_detection(self):
        self.assertFalse(needs_romanization("Café déjà vu"))
        self.assertTrue(needs_romanization("こんにちは"))
        self.assertEqual(detect_song_language(["夜に駆ける", "さよなら"]), "ja")
        self.assertEqual(detect_song_language(["月亮代表我的心"]), "zh")
        self.assertEqual(detect_song_language(["안녕하세요"]), "ko")

    def test_position_extrapolation(self):
        s = PlaybackState(TrackInfo("a", "b", duration=10), playing=False, position=3)
        self.assertEqual(s.current_position(), 3)


if __name__ == "__main__":
    unittest.main()
