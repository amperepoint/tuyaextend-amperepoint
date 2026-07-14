# Basic charging planner (v0.5)

The AmperePoint planner is a Home Assistant-side scheduler. It deliberately
does not encode the weekly plan into Tuya DP19 `local_timer`: the tested Q11
firmware exposes only one whole-hour start/end pair there, while this planner
supports multiple windows, weekdays and minute precision.

## Execution model

Every active window contains weekdays, start/end times and a current limit.
Windows that cross midnight belong to the weekday on which they start. If
windows overlap, the higher `priority` wins; equal priorities prefer the most
recent start.

The desired state is evaluated after startup, every minute, after coordinator
updates and after configuration or override changes. Starting a window uses
three separately confirmed Tuya operations:

1. select `charge_now`,
2. apply the window current limit,
3. enable charging.

Stopping a window disables charging. Each operation stays `pending` until the
coordinator reports the expected state. A missing confirmation fails after 45
seconds and is retried after five minutes. The last result remains visible on
the planner sensor and dashboard card.

## Manual override

Manual actions take precedence over the weekly plan:

- `charge` runs for the selected number of minutes;
- `energy` records the total/session meter baseline and stops after the
  requested delta in kWh;
- `pause` stops charging until the next planned window;
- `clear` returns immediately to the weekly plan.

The main dashboard Start/Stop button also uses an override while the planner is
enabled, preventing direct commands from fighting the next minute evaluation.

## Persistence and safety

The normalized windows, enabled flag, override and command result are stored
with Home Assistant's `Store` helper under the integration config entry. After
a restart, interrupted commands are reconciled with current reported values and
the desired plan is evaluated again. The planner is disabled with no windows on
first installation, so installing or upgrading alone cannot start a charger.

