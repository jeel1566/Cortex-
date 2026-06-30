from app.ingestion.engine_models import NormalizedSourceBundle

class ConnectorAdapter:
    def discover(self) -> list:
        """Discover source objects from the connector."""
        raise NotImplementedError

    def fetch(self, external_id: str) -> dict:
        """Fetch raw content or metadata for a source object."""
        raise NotImplementedError

    def extract(self, raw_data: dict) -> dict:
        """Extract structured document and segments from raw data."""
        raise NotImplementedError

    def normalize(self) -> NormalizedSourceBundle:
        """Normalize connector output into a shared NormalizedSourceBundle."""
        raise NotImplementedError
