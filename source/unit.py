import unittest
import findfunc
class conversionfuncs(unittest.TestCase):
    li = [("%artist% - %title%", "Artist - Title", {"artist": "Artist", "title": "Title"}),
    ("%artist% - %track% - %title%", "Artist - 01 - Title", {"artist": "Artist", "title": "Title", "track": "01"}),
    ("%artist% - %track% - %title% - %artist% - %title%", "Artist - 01 - Title - Artist2 - Title2", {"artist": "ArtistArtist2", "title": "TitleTitle2", "track": "01"})]
    
    def filetag(self):
        for z in li:
            self.assertEqual(findfunc.filenametotag(z[0],z[1]), z[2])

if __name__ == "__main__":
    unittest.main()
    
    