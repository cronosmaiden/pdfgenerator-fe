import http from 'k6/http';
import { check } from 'k6';

// --- CONFIGURA AQUI ---
const URL   = 'http://localhost:8000/generar_pdf/';
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyYWxib3Jub3oiLCJleHAiOjE3NDc2Nzk5ODl9.v4jbcANSvasdoF0EKEsDi5peiuz6AaDzAlvSzpSyos4';

// Carga el payload JSON desde el fichero
const payload = JSON.parse(open('payload.json', 'utf8'));

export let options = {
  scenarios: {
    load_test: {
      executor:      'constant-arrival-rate',
      rate:          10,      // 10 requests por segundo
      timeUnit:      '1s',
      duration:      '30s',   // durante 30 segundos
      preAllocatedVUs: 10,
      maxVUs:        60,
    },
  },
  thresholds: {
    http_req_duration: ['avg<500','p(95)<1000'],  // latencias aceptables
    checks:            ['rate>0.95'],              // al menos 95% de checks OK
  },
};

export default function () {
  let params = {
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${TOKEN}`,
    },
  };

  // IMPORTANTE: stringify para que llegue JSON válido al servicio
  let res = http.post(URL, JSON.stringify(payload), params);

  check(res, {
    'status 200': (r) => r.status === 200,
  });
}