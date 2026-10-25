"""Pure-Python tests (no Qt, no network). Run:  python -m unittest discover -s tests -v"""
import sys, unittest, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from lyricpip.lyrics.lrc import parse_lrc, parse_plain
from lyricpip.lyrics.matching import best_match
from lyricpip.models import PlaybackState, TrackInfo
from lyricpip.romanize import needs_romanization, detect_song_language
from lyricpip.textutil import clean_title, query_variants


class LrcTests(unittest.TestCase):
    def test_basic_and_multi_stamp(self):
        lines = parse_lrc("[ar:X]\n[00:01.50] hello\n[00:10.00][00:50.5] chorus\n")
        self.assertEqual([(l.time, l.text) for l in lines],
                         [(1.5, "hello"), (10.0, "chorus"), (50.5, "chorus")])

    def test_offset_and_word_tags(self):
        lines = parse_lrc("[offset:500]\n[00:02.00]<00:02.00>hi <00:02.40>there")
        self.assertEqual((lines[0].time, lines[0].text), (1.5, "hi there"))

    def test_plain(self):
        self.assertEqual([l.text for l in parse_plain("a\r\nb")], ["a", "b"])


class TextTests(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(clean_title("Song (Official Video) [4K] feat. Bob"), "Song")

    def test_variants_split_artist_title(self):
        v = query_variants(TrackInfo("Queen - Bohemian Rhapsody (Official Video)", "QueenVEVO"))
        self.assertIn(("Queen", "Bohemian Rhapsody"), [(t.artist, t.title) for t in v])


class MatchTests(unittest.TestCase):
    def test_duration_breaks_tie(self):
        t = TrackInfo("Yesterday", "The Beatles", duration=125)
        pick = best_match(t, [("live", "Yesterday", "The Beatles", 200),
                              ("studio", "Yesterday", "The Beatles", 126)])
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
