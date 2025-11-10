import http from 'k6/http';
import { check } from 'k6';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

export let options = {
  stages: [
    { duration: '5s', target: 500 }, // ramp-up to 10 users
  ],
};

export default function () {
  // Step 1: Get the CSRF token
  let response = http.get('http://localhost:8000/events/perftest');
  let csrfToken = response.html().find('input[name="csrfmiddlewaretoken"]').attr('value');

  let uuid = uuidv4();

  // Step 2: Post the form data with the CSRF token
  let formData = {
    csrfmiddlewaretoken: csrfToken,
    // Add your form fields here
    user: 'test',
    email: uuid + '@test.datateknologerna.org',
  };

  let headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Referer': 'http://localhost:8000/events/perftest',
    'Cookie': response.headers['Set-Cookie'],
  };

  let postResponse = http.post('http://localhost:8000/events/perftest/', formData, { headers: headers });

  // Step 3: Check the response
  check(postResponse, {
    'status is 200': (r) => r.status === 200,
    // Add more checks as needed
  });
}
