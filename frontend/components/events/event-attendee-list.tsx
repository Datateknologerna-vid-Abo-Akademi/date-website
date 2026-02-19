import type { EventAttendeeListPayload } from "@/lib/api/types";

interface EventAttendeeListProps {
  data: EventAttendeeListPayload | null;
}

export function EventAttendeeList({ data }: EventAttendeeListProps) {
  if (!data) {
    return <h4 id="no-attendee">Deltagarlistan är inte tillgänglig just nu.</h4>;
  }
  if (!data.show_attendee_list) {
    return <h4 id="no-attendee">Deltagarlistan är dold för tidigare evenemang.</h4>;
  }
  if (data.attendees.length === 0) {
    return <p id="no-attendee">Inga anmälda ännu, var den första!</p>;
  }

  return (
    <div className="table-wrap">
      {data.sign_up_max_participants !== 0 ? <p>Det finns {data.sign_up_max_participants} platser!</p> : null}
      <h2>Anmälda</h2>
      <table className="attendee-table" id="attendees">
        <thead>
          <tr id="attendees-header">
            <th>#</th>
            <th>Namn</th>
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
    </div>
  );
}
