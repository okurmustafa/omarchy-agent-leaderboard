# Agent Leaderboard

An Omarchy bar widget that ranks **token usage across every coding agent** on this machine.

It is a comparison board, not a per-subscription meter. The first-party Agents widget still owns limits, pace, and the model breakdown for one tool at a time. This panel answers a different question: *who is spending the tokens?*

The board is display-only. It watches the usage records that `omarchy-agent-usage-update` writes to `~/.local/state/omarchy/agents/usage/` and ranks whatever appears there. Claude, Codex, Fireworks, and the local Grok collector are enabled by default. Any other collector that writes the same record contract — Hermes, a future agent — shows up on the next refresh. The Grok mark is a stand-in until Omarchy ships one. The same files live in `~/.config/omarchy/agents/assets/` and in the cloned Agents plugin (`mustafaokur.agents`) so the first-party-style panel can show Grok too.

## Install

From a git checkout:

```sh
omarchy plugin add https://github.com/okurmustafa/omarchy-agent-leaderboard.git --enable
```

Or, while developing this folder:

```sh
ln -sfn "$PWD" ~/.config/omarchy/plugins/mustafaokur.agent-leaderboard
omarchy-shell shell rescanPlugins
omarchy plugin enable mustafaokur.agent-leaderboard --section right
```

The widget lands on the right of the bar, in the **AI** category next to Agents. A panel preview is in `preview.png`. Move it with:

```sh
omarchy bar move mustafaokur.agent-leaderboard --section right
```

## Usage

- Left click: open or close the panel
- Right click: launch an agent
- Middle click: next ranking window (today → 7 days → all-time)
- Escape: close
- `h` / `l` or left / right: change the ranking window
- `j` / `k` or up / down: move the selected standing
- `R` or Enter: refresh
- Tab: hand off to the neighboring bar panel

The panel ranks the selected window and draws a last-seven-days chart. Per-model totals stay in the first-party Agents widget.

Summon without the bar:

```sh
omarchy-shell shell summon mustafaokur.agent-leaderboard '{}'
omarchy-shell shell hide mustafaokur.agent-leaderboard
```

## How ranking is computed

Each usage record already carries the numbers the first-party collectors publish:

| Window | Source |
|---|---|
| **Today** | `todayTotalTokens` |
| **7 days** | sum of `recentDays[].messageCount` (those values are token totals, despite the name) |
| **All-time** | sum of every `modelUsage` bucket, floored by the week and today totals when a collector only knows a recent window |

Agents with no tokens in the selected window are omitted from that board. An agent that has never recorded usage does not appear at all. The bar icon itself stays hidden until at least one enabled agent has usage.

Claude, Codex, and Fireworks are refreshed through `omarchy-agent-usage-update`. Other records in the usage directory are read as-is.

## Configure

Settings live on the widget's entry in `~/.config/omarchy/shell.json`:

| Key | Default | What it does |
|---|---|---|
| `refreshIntervalSec` | `900` | How often the usage records regenerate |
| `period` | `"today"` | Opening ranking window: `today`, `week`, or `all` |

```sh
omarchy bar set mustafaokur.agent-leaderboard refreshIntervalSec 300 --json
omarchy bar set mustafaokur.agent-leaderboard period week
```

Per-agent enablement is nested. Pass the whole `providers` object (or edit `shell.json` directly):

```sh
omarchy bar set mustafaokur.agent-leaderboard providers '{
  "claude": { "enabled": true },
  "codex": { "enabled": true },
  "fireworks": { "enabled": true }
}' --json
```

`enabled` defaults to `true` for every discovered agent; set it to `false` to hide one.

## Validate

```sh
omarchy plugin validate .
qmllint -I "$OMARCHY_PATH/shell" Agent.qml Main.qml Panel.qml
node test/model-test.js
```

## Remove

```sh
omarchy plugin remove mustafaokur.agent-leaderboard
```

That deletes the plugin folder. It does **not** remove `~/.local/state/omarchy/agents/usage/`.

## Attribution

- Panel structure and the Claude / Codex / Fireworks marks follow Omarchy’s first-party Agents widget (MIT, David Heinemeier Hansson / Omarchy).
- The Hermes mark is traced from the official Hermes Desktop icon (MIT, [Nous Research](https://github.com/NousResearch/hermes-agent)).
- The Grok mark follows the current singularity-G brand path. Replace it with Omarchy’s official asset when that ships.
- Ranking reads the same usage records that `omarchy-agent-usage-update` already writes.

## License

MIT — see [LICENSE](LICENSE).
