import http from 'k6/http';
import { check } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 50 },
    { duration: '30s', target: 50 },
    { duration: '5s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(99)<50'],
  },
};

export default function () {
  const res = http.get('http://localhost:8000/loadtest', {
    headers: { 'x-api-key': `user-${__VU}` },
  });
  check(res, { 'status is 200': (r) => r.status === 200 });
}