// noinspection DuplicatedCode
$(function() {

    // for HTTPS also use WSS.
    let ws_scheme = window.location.protocol === "https:" ? "wss" : "ws";
    let socket = new WebSocket(ws_scheme + '://' + window.location.host + '/ws' + window.location.pathname);

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
    socket.onclose = function(e) {
        console.error('Event socket closed unexpectedly');
    };

});
