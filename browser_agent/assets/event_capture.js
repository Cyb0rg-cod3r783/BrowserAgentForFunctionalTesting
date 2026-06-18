/**
 * event_capture.js
 * Injected into every page during recording via page.evaluate() after each navigation.
 * Captures click, input, change, and submit events into window.__capturedEvents.
 * Uses capture:true listeners to intercept all events from the document root.
 * Prevents duplicate listeners per page load via window.__listenersAttached.
 */
(function () {
    try {
        // Always (re-)initialize the events array on each inject
        if (!window.__capturedEvents) {
            window.__capturedEvents = [];
        }

        // Prevent duplicate listener attachment within the same page context
        if (window.__listenersAttached) {
            return;
        }
        window.__listenersAttached = true;

        /**
         * Extract metadata from a DOM element safely.
         */
        function extractElementData(target) {
            try {
                var classes = [];
                try {
                    if (target.className && typeof target.className === 'string') {
                        classes = target.className.split(/\s+/).filter(Boolean).slice(0, 5);
                    }
                } catch (e) {}

                var textContent = '';
                try {
                    textContent = (target.innerText || target.value || '').substring(0, 200);
                } catch (e) {}

                var ariaLabel = null;
                var role = null;
                try {
                    ariaLabel = target.getAttribute('aria-label');
                    role = target.getAttribute('role');
                } catch (e) {}

                var isFormControl = false;
                try {
                    isFormControl = ['INPUT', 'TEXTAREA', 'SELECT'].indexOf(target.tagName) !== -1;
                } catch (e) {}

                return {
                    tag: target.tagName ? target.tagName.toLowerCase() : null,
                    type_attr: target.type || null,
                    id: target.id || null,
                    name: target.name || null,
                    placeholder: target.placeholder || null,
                    aria_label: ariaLabel,
                    role: role,
                    text_content: textContent,
                    value: isFormControl ? (target.value || null) : null,
                    classes: classes
                };
            } catch (e) {
                return { tag: null };
            }
        }

        /**
         * Returns a handler for the given event type.
         */
        function makeHandler(eventType) {
            return function (e) {
                try {
                    var target = e.target;
                    if (!target || !target.tagName) return;

                    var data = extractElementData(target);
                    data.event_type = eventType;
                    data.timestamp = Date.now();
                    data.page_url = window.location.href;

                    window.__capturedEvents.push(data);
                } catch (err) {
                    // Never throw from event handlers
                }
            };
        }

        // Attach all listeners with capture:true (intercept before target)
        var eventTypes = ['click', 'input', 'change', 'submit'];
        for (var i = 0; i < eventTypes.length; i++) {
            document.addEventListener(eventTypes[i], makeHandler(eventTypes[i]), true);
        }

    } catch (globalErr) {
        // Silently swallow all top-level errors
    }
})();
