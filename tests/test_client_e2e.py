
import os 
import pandas as pd
import pytest

from src.pyrox.core import PyroxClient

@pytest.mark.integration
def test_get_season_somke():
    """
    Very simple end-to-end smoke test against the live CDN.
    """

    client = PyroxClient()
    df = client.get_season(season=7)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    assert (set(df['division'])) == set(['doubles', 'open', 'pro'])
    assert (set(df['gender'])) == set(['male', 'mixed', 'female'])
    assert len(df) > 1000

