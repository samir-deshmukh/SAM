import http from 'k6/http';
import { check, sleep } from 'k6';
export const options = {
  stages: [{duration:'20s',target:10},{duration:'40s',target:10},{duration:'10s',target:0}],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{page:home}': ['p(95)<1000'],
    'http_req_duration{page:options}': ['p(95)<1000'],
  },
};
export function setup(){ http.get('https://cetfind.onrender.com/',{timeout:'90s'}); http.get('https://cetfind-backend.onrender.com/api/options',{timeout:'90s'}); }
export default function () {
  let r = http.get('https://cetfind.onrender.com/',{tags:{page:'home'}});
  check(r,{'home 200':x=>x.status===200});
  r = http.get('https://cetfind-backend.onrender.com/api/options',{tags:{page:'options'}});
  check(r,{'options 200':x=>x.status===200});
  sleep(3);
}
