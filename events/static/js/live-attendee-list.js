// noinspection DuplicatedCode
$(function() {

    // for HTTPS also use WSS.
    let ws_scheme = window.location.protocol === "https:" ? "wss" : "ws";
    let socket = new WebSocket(ws_scheme + '://' + window.location.host + '/ws' + window.location.pathname);

    socket.onmessage = function(e) {
        let data = JSON.parse(e.data);
        data = data.data;

        let list = $('#attendees tbody');
        $('#attendees-header').css("display", "table-row");
        $('#no-attendee').css("display", "none");

        if(data) {
            let attendee = '<tr><td>' + list[0].childElementCount + '</td>';
            for (let key in data) {
                if (!data.hasOwnProperty(key)) continue;
                attendee += '<td>' + data[key] + '</td>';
            }
            attendee += '</tr>';
            list.append(attendee);
        }
    };
    socket.onclose = function(e) {
        console.error('Event socket closed unexpectedly');
    };

});