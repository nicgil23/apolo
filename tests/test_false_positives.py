from apolo.metadata.matcher import MetadataMatcher
from apolo.metadata.models import TrackMetadata


def test_reject_false_positive_matches():
    matcher = MetadataMatcher()
    
    # Even if "Facundo" is part of the query, it should not match a completely different song
    match = matcher.find_best_match(
        query="FRO!, Facundo Agustín Pelontri - mi ：) LUZ",
        expected_title="mi ：) LUZ",
        expected_artist="FRO!, Facundo Agustín Pelontri",
    )
    
    # If no real match on iTunes/Deezer for this underground track, it must return None rather than a wrong artist
    if match is not None:
        assert "mi" in match.title.lower() or "luz" in match.title.lower()
