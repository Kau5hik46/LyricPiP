"""macOS watcher tests. No osascript, no thread start, so they run on any OS."""

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from lyricpip.media.macos_applescript import parse_players

# Real script output captured from Music.app (durations in seconds).
MUSIC = {"player": "Music", "state": "paused", "title": "Bad Luck", "artist": "Adam Jensen",
         "album": "Bad Luck - Single", "duration": 202.3699951171875,
         "position": 2.6040000915527344}
# Spotify's dictionary reports duration in milliseconds, position in seconds.
SPOTIFY = {"player": "Spotify", "state": "playing", "title": "Bohemian Rhapsody",
           "artist": "Queen", "album": "A Night at the Opera", "duration": 354320,
           "position": 12.5}


def nothing_ignored(player: str) -> bool:
    return False


def parse(*snapshots, is_ignored=nothing_ignored):
    return parse_players(json.dumps(list(snapshots)), is_ignored)


class ParsePlayersTests(unittest.TestCase):
    def test_snapshot_becomes_track_and_position(self):
        state = parse(SPOTIFY)
        track = state.track
        self.assertEqual(
            (track.title, track.artist, track.album, track.player),
            ("Bohemian Rhapsody", "Queen", "A Night at the Opera", "Spotify"),
        )
        self.assertEqual((state.playing, state.position), (True, 12.5))

    def test_spotify_duration_milliseconds_become_seconds(self):
        self.assertAlmostEqual(parse(SPOTIFY).track.duration, 354.32)

    def test_music_duration_stays_in_seconds(self):
        self.assertAlmostEqual(parse(MUSIC).track.duration, 202.3699951171875)

    def test_missing_duration_is_unknown(self):
        no_duration = {k: v for k, v in MUSIC.items() if k != "duration"}
        self.assertIsNone(parse(no_duration).track.duration)

    def test_playing_player_beats_paused_one(self):
        state = parse({**SPOTIFY, "state": "paused"}, {**MUSIC, "state": "playing"})
        self.assertEqual(state.track.player, "Music")

    def test_script_order_breaks_tie_when_nothing_plays(self):
        state = parse({**SPOTIFY, "state": "paused"}, MUSIC)
        self.assertEqual(state.track.player, "Spotify")

    def test_ignored_player_is_skipped(self):
        state = parse(SPOTIFY, MUSIC, is_ignored=lambda player: player == "Spotify")
        self.assertEqual(state.track.player, "Music")

    def test_snapshot_without_title_is_skipped(self):
        state = parse({**SPOTIFY, "title": ""}, MUSIC)
        self.assertEqual(state.track.player, "Music")

    def test_no_running_player_gives_empty_state(self):
        state = parse()
        self.assertEqual((state.track, state.playing), (None, False))

    def test_invalid_json_gives_empty_state_and_logs(self):
        with self.assertLogs("lyricpip.media.macos_applescript", "WARNING"):
            state = parse_players("execution error", nothing_ignored)
        self.assertIsNone(state.track)


if __name__ == "__main__":
    unittest.main()
