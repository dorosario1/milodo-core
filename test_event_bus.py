import unittest

from event_bus import clear, emit, subscribe


class EventBusTests(unittest.TestCase):
    def setUp(self):
        clear()

    def tearDown(self):
        clear()

    def test_subscribe_and_emit(self):
        calls = []

        def handler(payload):
            calls.append(payload)

        subscribe("task_done", handler)
        emit("task_done", {"task": "build"})

        self.assertEqual(calls, [{"task": "build"}])

    def test_multiple_handlers(self):
        calls = []

        def first(payload):
            calls.append(("first", payload))

        def second(payload):
            calls.append(("second", payload))

        subscribe("task_done", first)
        subscribe("task_done", second)
        emit("task_done", {"task": "build"})

        self.assertEqual(
            calls,
            [
                ("first", {"task": "build"}),
                ("second", {"task": "build"}),
            ],
        )

    def test_no_subscriber(self):
        emit("missing_event", {"ok": True})

    def test_handler_exception(self):
        calls = []

        def failing(payload):
            raise Exception("boom")

        def second(payload):
            calls.append(payload)

        subscribe("task_done", failing)
        subscribe("task_done", second)
        emit("task_done", {"task": "build"})

        self.assertEqual(calls, [{"task": "build"}])

    def test_clear(self):
        calls = []

        def handler(payload):
            calls.append(payload)

        subscribe("task_done", handler)
        clear()
        emit("task_done", {"task": "build"})

        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
