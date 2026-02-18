import type { EventAttendeeListPayload } from "@/lib/api/types";

interface EventAttendeeListProps {
  data: EventAttendeeListPayload | null;
}

export function EventAttendeeList({ data }: EventAttendeeListProps) {
  if (!data) {
    return <p className="meta">Attendee list is unavailable right now.</p>;
  }
  if (!data.show_attendee_list) {
    return <p className="meta">Attendee list is hidden for past events.</p>;
  }
  if (data.attendees.length === 0) {
    return <p className="meta">No attendees yet.</p>;
  }

  return (
    <div className="table-wrap">
      <table className="attendee-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Name</th>
            {data.registration_public_fields.map((fieldName) => (
              <th key={fieldName}>{fieldName}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.attendees.map((attendee) => (
            <tr key={`${attendee.position}-${attendee.display_name}`} className={attendee.is_waitlist ? "is-waitlist" : ""}>
              <td>{attendee.position}</td>
              <td>{attendee.display_name}</td>
              {attendee.fields.map((field) => (
                <td key={`${attendee.position}-${field.name}`}>{field.value}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.sign_up_max_participants !== 0 ? (
        <p className="meta">Capacity: {data.sign_up_max_participants}</p>
      ) : null}
    </div>
  );
}
