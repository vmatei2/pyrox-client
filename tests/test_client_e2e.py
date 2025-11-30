
import os 
import pandas as pd
import pytest

from src.pyrox.core import PyroxClient
from src.pyrox.errors import AthleteNotFound

@pytest.mark.integration
def test_get_season_somke():
    """
    Very simple end-to-end get_season smoke test against the live CDN.
    """

    client = PyroxClient()
    df = client.get_season(season=7)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    assert (set(df['division'])) == set(['doubles', 'open', 'pro'])
    assert (set(df['gender'])) == set(['male', 'mixed', 'female'])
    assert len(df) > 1000

@pytest.mark.integration
def test_get_athlete_smoke():
    """
    Very simple get athlete end-to-end smoke test against the live cdn"""

    client = PyroxClient()
    df = client.get_athlete_in_race(season=7, location="Barcelona", athlete_name="Matei")

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df['age_group'][0] == '25-29'
    assert df['wallBalls_time'][0] > 6.0 # :( 

    with pytest.raises(AthleteNotFound):
        df = client.get_athlete_in_race(season=7, location="Barcelona", athlete_name="NonExistentAthlete123")
