# Phase 3 JMeter Test

`online_boutique_load_test.jmx` tests the Online-Boutique shopping flow through
HTTP requests:

1. `GET /`
2. `GET /product/OLJCESPC7Z`
3. `POST /cart`
4. `GET /cart`
5. `POST /cart/checkout`

The test plan includes an HTTP Cookie Manager so cart and checkout requests stay
within the same user session.

## Run

Make sure the frontend is available at `http://127.0.0.1:8088`.

Smoke test:

```powershell
cd D:\Study\SoftwareTesting
.\FinalProject\scripts\run-phase3-jmeter.ps1 -Threads 1 -Loops 1 -RunName smoke-001
```

Normal load:

```powershell
.\FinalProject\scripts\run-phase3-jmeter.ps1 -Threads 10 -RampUp 20 -Loops 5 -RunName normal-001
```

Higher local load:

```powershell
.\FinalProject\scripts\run-phase3-jmeter.ps1 -Threads 20 -RampUp 30 -Loops 5 -RunName higher-001
```

Outputs are written to `FinalProject/data/phase3/jmeter/<run-name>/`.

## Metrics To Report

Use the generated HTML dashboard and `.jtl` file to report:

- average response time
- median response time
- 90% / 95% / 99% response time
- throughput
- error percentage
- total samples
