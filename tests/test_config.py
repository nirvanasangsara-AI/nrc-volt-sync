from nrc_volt_sync.config import redact_config


def test_redacts_every_persisted_config_value() -> None:
    config = {
        "garmin_email": "runner@example.com",
        "strava_athlete_id": 123456,
        "strava_client_id": "654321",
        "strava_client_secret": "secret-value",
        "future_private_field": "private-value",
    }

    assert redact_config(config) == {key: "<stored>" for key in config}
