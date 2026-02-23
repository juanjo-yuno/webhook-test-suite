from src.models.webhook import WebhookEvent
from src.webhook_simulator.engine import WebhookDeliveryEngine
from src.webhook_simulator.logger import DeliveryLogger
from src.models.delivery import DeliveryAttempt


class WebhookReplayManager:
    """Replays previously delivered webhook events."""

    def __init__(self, engine: WebhookDeliveryEngine, logger: DeliveryLogger):
        self.engine = engine
        self.logger = logger
        self._events: dict[str, WebhookEvent] = {}

    def register_event(self, event: WebhookEvent) -> None:
        """Store an event for potential replay."""
        self._events[event.event_id] = event

    def replay_event(self, event_id: str, url: str) -> list[DeliveryAttempt]:
        """Replay a specific event by ID to the given URL.

        The replayed delivery is marked in the payload with replay=True.
        """
        event = self._events.get(event_id)
        if event is None:
            raise ValueError(f"Event {event_id} not found for replay")

        # Create a replay copy with replay marker
        replay_payload = dict(event.payload)
        replay_payload["_replay"] = True

        replay_event = WebhookEvent(
            event_id=event.event_id,
            payment_id=event.payment_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            payload=replay_payload,
            signature="",
        )

        return self.engine.deliver_with_retry(replay_event, url, delay_factor=0)

    def replay_failed(self, url: str) -> dict[str, list[DeliveryAttempt]]:
        """Replay all events that had failed deliveries.

        Returns a dict mapping event_id to list of delivery attempts.
        """
        failed_attempts = self.logger.get_failed_attempts()
        failed_event_ids = {a.event_id for a in failed_attempts}

        results = {}
        for event_id in failed_event_ids:
            if event_id in self._events:
                results[event_id] = self.replay_event(event_id, url)

        return results

    def get_registered_events(self) -> dict[str, WebhookEvent]:
        return dict(self._events)
