"""Test that disable_screenshot_pipeline switch correctly controls screenshot capture in browser state flow.

Task 1: Default config disables screenshot pipeline.
Task 2: Explicit disable_screenshot_pipeline=False restores screenshot behavior.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from browser_use.browser.events import BrowserStateRequestEvent
from browser_use.browser.profile import BrowserProfile

# =========================================================================
# Task 1: Default disable_screenshot_pipeline=True
# =========================================================================


def test_browser_profile_has_disable_screenshot_pipeline_field():
	"""BrowserProfile should expose disable_screenshot_pipeline with default True."""
	profile = BrowserProfile()
	assert hasattr(profile, 'disable_screenshot_pipeline'), 'BrowserProfile must have a disable_screenshot_pipeline field'
	assert profile.disable_screenshot_pipeline is True, (
		'disable_screenshot_pipeline should default to True (screenshots disabled by default)'
	)


def test_browser_state_request_event_include_screenshot_defaults_true():
	"""BrowserStateRequestEvent.include_screenshot should still default to True (unchanged event semantics)."""
	event = BrowserStateRequestEvent()
	assert event.include_screenshot is True


@pytest.mark.asyncio
async def test_default_disable_screenshot_pipeline():
	"""When BrowserProfile.disable_screenshot_pipeline=True (default),
	get_browser_state_summary should dispatch BrowserStateRequestEvent with include_screenshot=False."""
	from browser_use.browser.session import BrowserSession

	profile = BrowserProfile(disable_screenshot_pipeline=True)
	session = BrowserSession(browser_profile=profile)

	dispatched_events: list[BrowserStateRequestEvent] = []

	def capture_dispatch(event):
		if isinstance(event, BrowserStateRequestEvent):
			dispatched_events.append(event)
		mock_event = AsyncMock()
		mock_event.event_result = AsyncMock(return_value=MagicMock(dom_state=MagicMock(selector_map={1: 'elem'})))
		return mock_event

	# Patch cached state to force a fresh dispatch
	session._cached_browser_state_summary = None

	mock_result = MagicMock()
	mock_result.dom_state = MagicMock(selector_map={1: 'elem'})

	with patch.object(session.event_bus, 'dispatch', side_effect=capture_dispatch):
		await session.get_browser_state_summary()

	assert len(dispatched_events) == 1, 'Expected exactly one BrowserStateRequestEvent to be dispatched'
	assert dispatched_events[0].include_screenshot is False, (
		f'Expected include_screenshot=False when disable_screenshot_pipeline=True, '
		f'got include_screenshot={dispatched_events[0].include_screenshot}'
	)


# =========================================================================
# Task 2: Explicit disable_screenshot_pipeline=False restores screenshots
# =========================================================================


def test_browser_profile_disable_screenshot_pipeline_false():
	"""BrowserProfile(disable_screenshot_pipeline=False) should allow screenshots."""
	profile = BrowserProfile(disable_screenshot_pipeline=False)
	assert profile.disable_screenshot_pipeline is False


@pytest.mark.asyncio
async def test_enable_screenshot_pipeline_explicitly():
	"""When BrowserProfile.disable_screenshot_pipeline=False,
	get_browser_state_summary should dispatch BrowserStateRequestEvent with include_screenshot=True."""
	from browser_use.browser.session import BrowserSession

	profile = BrowserProfile(disable_screenshot_pipeline=False)
	session = BrowserSession(browser_profile=profile)

	dispatched_events: list[BrowserStateRequestEvent] = []

	def capture_dispatch(event):
		if isinstance(event, BrowserStateRequestEvent):
			dispatched_events.append(event)
		mock_event = AsyncMock()
		mock_event.event_result = AsyncMock(return_value=MagicMock(dom_state=MagicMock(selector_map={1: 'elem'})))
		return mock_event

	session._cached_browser_state_summary = None

	with patch.object(session.event_bus, 'dispatch', side_effect=capture_dispatch):
		await session.get_browser_state_summary()

	assert len(dispatched_events) == 1, 'Expected exactly one BrowserStateRequestEvent to be dispatched'
	assert dispatched_events[0].include_screenshot is True, (
		f'Expected include_screenshot=True when disable_screenshot_pipeline=False, '
		f'got include_screenshot={dispatched_events[0].include_screenshot}'
	)


# =========================================================================
# Task 2: Log marker verification
# =========================================================================


@pytest.mark.asyncio
async def test_screenshot_pipeline_disabled_log_marker():
	"""When pipeline is disabled, debug log should contain 'screenshot_pipeline=disabled'."""

	from browser_use.browser.session import BrowserSession

	profile = BrowserProfile(disable_screenshot_pipeline=True)
	session = BrowserSession(browser_profile=profile)
	session._cached_browser_state_summary = None

	def dummy_dispatch(*args, **kwargs):
		mock_result = MagicMock()
		mock_result.dom_state = MagicMock(selector_map={1: 'elem'})
		mock_event_obj = AsyncMock()
		mock_event_obj.event_result = AsyncMock(return_value=mock_result)
		return mock_event_obj

	log_msgs = []
	original_debug = session.logger.debug

	def mock_debug(msg, *args, **kwargs):
		log_msgs.append(msg)
		original_debug(msg, *args, **kwargs)

	with (
		patch.object(session.event_bus, 'dispatch', side_effect=dummy_dispatch),
		patch.object(session.logger, 'debug', side_effect=mock_debug),
	):
		await session.get_browser_state_summary()

	assert any('screenshot_pipeline=disabled' in msg for msg in log_msgs), (
		f'Expected log message containing "screenshot_pipeline=disabled", got: {log_msgs}'
	)
