// noinspection DuplicatedCode
$(function() {

    // for HTTPS also use WSS.
    const ws_scheme = window.location.protocol === "https:" ? "wss" : "ws";

    const attendeeListEl = document.getElementById('attendee-list');
    const parentSlug = attendeeListEl ? attendeeListEl.dataset.parentSlug : '';

    // Child events store their attendees on the parent and ws_send broadcasts
    // to the parent slug's group, so both branches must hit the single
    // ws/events/<slug>/ route (event routing only knows that path).
    let ws_url;
    if (parentSlug) {
        ws_url = ws_scheme + '://' + window.location.host + '/ws/events/' + parentSlug + '/';
    } else {
        ws_url = ws_scheme + '://' + window.location.host + '/ws' + window.location.pathname;
    }

    let socket = null;
    let reconnectDelay = 1000;
    let closedByPage = false;

    function connect() {
        socket = new WebSocket(ws_url);

        socket.onmessage = function(e) {
            const { fields, anonymous } = JSON.parse(e.data).data;

            const list = $('#attendees tbody');
            $('#attendees-header').css("display", "table-row");
            $('#no-attendee').css("display", "none");

            if (fields) {
                // includes header row and is thus equivalent to current amount of attendees + 1
                const attendeeNumber = list.children().length;
                const row = $('<tr>');
                row.append($('<td>').text(attendeeNumber));
                for (const [field, value] of fields) {
                    const cell = $('<td>');
                    // names of anonymous attendees use <i>
                    if (field === "user" && anonymous)
                        cell.append($('<i>').text(value))
                    else
                        cell.text(value);
                    row.append(cell);
                }
                list.append(row);
            }
        };

        socket.onopen = function() {
            reconnectDelay = 1000;
        };

        socket.onclose = function() {
            if (closedByPage) {
                return;
            }
            // Worker recycling, deploys and network blips close the socket;
            // keep the live list refreshing instead of going stale silently.
            // Retry with capped exponential backoff (1s doubling to 30s).
            console.warn('Event socket closed; reconnecting in ' + reconnectDelay + 'ms');
            setTimeout(connect, reconnectDelay);
            reconnectDelay = Math.min(reconnectDelay * 2, 30000);
        };

        socket.onerror = function() {
            socket.close();
        };
    }

    connect();

    // Stop retrying once the page is being left.
    window.addEventListener('beforeunload', function() {
        closedByPage = true;
        socket.close();
    });

    // Back/forward cache restore keeps the page alive but the socket died
    // with the freeze; resume updates instead of staying permanently closed
    // (closedByPage is still set from the beforeunload that preceded it).
    window.addEventListener('pageshow', function() {
        closedByPage = false;
        if (!socket || socket.readyState === WebSocket.CLOSED) {
            reconnectDelay = 1000;
            connect();
        }
    });

});
