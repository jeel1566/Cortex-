from typing import List, Dict, Any, Optional
from app.ingestion.connectors.base import ConnectorAdapter
from app.ingestion.engine_models import (
    NormalizedSourceBundle,
    NormalizedSourceObject,
    NormalizedSourceDocument,
    NormalizedSourceSegment,
    NormalizedSourceRelationship,
)

class SlackAdapter(ConnectorAdapter):
    def __init__(self, tenant_id: str, client_token: str, channels: List[str]):
        self.tenant_id = tenant_id
        self.client_token = client_token
        self.channels = channels
        if self.client_token == "mock_slack_token":
            import os
            allow_mock = os.environ.get("ALLOW_MOCK_CONNECTORS", "").lower() in {"1", "true", "yes"}
            if not allow_mock:
                raise ValueError("SLACK_API_TOKEN is not configured. Set it or enable ALLOW_MOCK_CONNECTORS=1 for demo syncs.")

    def fetch_thread_replies(self, channel_id: str, thread_ts: str) -> List[Dict[str, Any]]:
        if self.client_token == "mock_slack_token":
            return [
                {"ts": thread_ts, "text": "Parent thread message", "user": "U123", "reactions": [{"name": "thumbsup", "count": 1}], "files": []},
                {"ts": "1719583200.0002", "text": "First reply message", "user": "U456", "reactions": [], "files": []},
            ]
        
        import requests
        url = "https://slack.com/api/conversations.replies"
        headers = {"Authorization": f"Bearer {self.client_token}"}
        params = {"channel": channel_id, "ts": thread_ts}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                return data.get("messages", [])
        except Exception as e:
            print(f"Error fetching Slack replies: {e}")
        return []

    def fetch_channel_history(self, channel_id: str) -> List[Dict[str, Any]]:
        if self.client_token == "mock_slack_token":
            return [
                {"ts": "1719583200.0001", "text": "Parent thread message", "user": "U123", "thread_ts": "1719583200.0001", "reactions": [{"name": "thumbsup", "count": 1}], "files": []}
            ]
        
        import requests
        url = "https://slack.com/api/conversations.history"
        headers = {"Authorization": f"Bearer {self.client_token}"}
        params = {"channel": channel_id}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                return data.get("messages", [])
        except Exception as e:
            print(f"Error fetching Slack history: {e}")
        return []

    def normalize(self) -> NormalizedSourceBundle:
        objects = []
        documents = []
        segments = []
        relationships = []

        for channel in self.channels:
            messages = self.fetch_channel_history(channel)
            threads = [m for m in messages if "thread_ts" in m]
            
            for thread in threads:
                thread_ts = thread["thread_ts"]
                replies = self.fetch_thread_replies(channel, thread_ts)
                if not replies:
                    replies = [thread]
                
                external_id = f"slack://channel/{channel}/thread/{thread_ts}"
                title = thread["text"][:30] + "..." if len(thread["text"]) > 30 else thread["text"]
                if not title.strip():
                    title = f"Slack Thread {thread_ts}"
                
                src_obj = NormalizedSourceObject(
                    tenant_id=self.tenant_id,
                    connector_type="slack",
                    external_id=external_id,
                    object_type="thread",
                    title=title,
                    url=f"https://slack.com/archives/{channel}/p{thread_ts.replace('.', '')}",
                    metadata={"channel": channel, "thread_ts": thread_ts},
                )
                objects.append(src_obj)
                
                body_text = "\n\n".join(f"{r.get('user', 'unknown')}: {r.get('text', '')}" for r in replies)
                doc = NormalizedSourceDocument(
                    source_object_external_id=external_id,
                    title=title,
                    body_text=body_text,
                    metadata={"channel": channel, "thread_ts": thread_ts},
                )
                documents.append(doc)
                
                for idx, r in enumerate(replies):
                    segments.append(NormalizedSourceSegment(
                        document_ref=external_id,
                        segment_type="message",
                        heading_path=[title],
                        position=idx,
                        text=r.get("text", ""),
                        author=r.get("user", "unknown"),
                        timestamp=r.get("ts", ""),
                        metadata={
                            "channel": channel,
                            "thread_ts": thread_ts,
                            "reactions": r.get("reactions", []),
                            "files": r.get("files", []),
                        }
                    ))
                    
        if not documents:
            raise ValueError("Zero messages discovered from Slack. Slack empty sync must fail loudly.")
            
        return NormalizedSourceBundle(
            tenant_id=self.tenant_id,
            connector_type="slack",
            objects=objects,
            documents=documents,
            segments=segments,
            relationships=relationships
        )
