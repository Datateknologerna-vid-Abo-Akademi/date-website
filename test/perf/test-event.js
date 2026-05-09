import http from 'k6/http';
import { check, fail } from 'k6';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

const TARGET_VUS = Number(__ENV.TARGET_VUS || 500);
const RAMP_DURATION = __ENV.RAMP_DURATION || '5s';
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const EVENT_SLUG = __ENV.EVENT_SLUG || 'perftest';
const EVENT_URL = `${BASE_URL}/events/${EVENT_SLUG}/`;

export let options = {
  stages: [
    { duration: RAMP_DURATION, target: TARGET_VUS },
  ],
};

export default function () {
  let response = http.get(EVENT_URL);
  check(response, {
    'event page is available': (r) => r.status === 200,
  }) || fail(`Expected ${EVENT_URL} to return 200. Create an event with slug "${EVENT_SLUG}" before running this test.`);

  let csrfToken = response.html().find('input[name="csrfmiddlewaretoken"]').attr('value');
  if (!csrfToken) {
    fail(`Could not find csrfmiddlewaretoken on ${EVENT_URL}. Make sure event signup is enabled and open.`);
  }

  let uuid = uuidv4();

  let formData = {
    csrfmiddlewaretoken: csrfToken,
    user: 'test',
    email: uuid + '@test.datateknologerna.org',
  };

  let headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Referer': EVENT_URL,
    'Cookie': response.headers['Set-Cookie'],
  };

  let postResponse = http.post(EVENT_URL, formData, { headers: headers });

  check(postResponse, {
    'status is 200': (r) => r.status === 200,
  });
}
