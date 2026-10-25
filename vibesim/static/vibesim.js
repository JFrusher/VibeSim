// VibeSim browser client, no dependencies. Served by the server at /client/vibesim.js.
//
//   const sim = await VibeSim.create("http://127.0.0.1:8000", { prompt: "5 vans in rainy Bristol" });
//   const stop = sim.stream((event) => console.log(event));     // SSE
//   const ws = sim.socket((event) => render(event));            // WebSocket
//   ws.inject({ name: "outage", drop_rate: 1, duration_ticks: 10 });
//   await sim.chaos("sudden network drop on half the vans");
(function (global) {
  "use strict";

  async function request(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) {
      throw new Error(`VibeSim ${response.status}: ${await response.text()}`);
    }
    return response.status === 204 ? null : response.json();
  }

  function post(url, body) {
    return request(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  }

  class Simulation {
    constructor(baseUrl, id) {
      this.baseUrl = baseUrl.replace(/\/$/, "");
      this.id = id;
      this.url = `${this.baseUrl}/simulations/${id}`;
    }

    state() { return request(`${this.url}/state`); }
    control(action) { return post(`${this.url}/${action}`, {}); }  // start | pause | step | stop
    advance(ticks) { return post(`${this.url}/advance?ticks=${ticks}`, {}); }
    inject(anomaly) { return post(`${this.url}/chaos`, anomaly); }
    chaos(prompt, compiler = "keyword") { return post(`${this.url}/chaos/prompt`, { prompt, compiler }); }
    remove(name) { return request(`${this.url}/chaos/${encodeURIComponent(name)}`, { method: "DELETE" }); }
    delete() { return request(this.url, { method: "DELETE" }); }

    // Server-Sent Events. Returns a function that closes the stream.
    stream(onEvent) {
      const source = new EventSource(`${this.url}/stream`);
      source.onmessage = (message) => onEvent(JSON.parse(message.data));
      return () => source.close();
    }

    // WebSocket: events in, anomalies out via .inject(anomaly).
    socket(onEvent) {
      const ws = new WebSocket(`${this.url.replace(/^http/, "ws")}/ws`);
      ws.onmessage = (message) => onEvent(JSON.parse(message.data));
      ws.inject = (anomaly) => ws.send(JSON.stringify(anomaly));
      return ws;
    }
  }

  const VibeSim = {
    // body: { prompt, compiler?, seed? } or { config }
    async create(baseUrl, body) {
      const created = await post(`${baseUrl.replace(/\/$/, "")}/simulations`, body);
      return new Simulation(baseUrl, created.simulation_id);
    },
    attach(baseUrl, id) { return new Simulation(baseUrl, id); },
    compile(baseUrl, prompt, compiler = "keyword") {
      return post(`${baseUrl.replace(/\/$/, "")}/compile`, { prompt, compiler });
    },
  };

  if (typeof module !== "undefined" && module.exports) module.exports = VibeSim;
  else global.VibeSim = VibeSim;
})(typeof window !== "undefined" ? window : globalThis);
