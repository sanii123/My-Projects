# Good Boy Protocol

Every dog owner is a confident narrator with zero evidence. "She's staring
because she wants a treat." "He's barking because he's mad." Pure
projection, no investigation.

This is an agent that isn't allowed to have an opinion about Luna until it's
checked. It exposes Luna's stats and needs as real MCP tools, lets Gemini
decide which ones to call and in what order, and shows you the entire
investigation, not just the conclusion.

## Architecture

```
dog_state.py     - Luna's state (energy, boredom, tail wag, meal/walk timing).
                    Lives in a small JSON file so multiple processes can
                    share it without a real database.

mcp_server.py     - Exposes dog_state as MCP tools: getters (get_energy_level,
                    get_minutes_since_last_meal, ...) and actions
                    (take_luna_for_walk, feed_luna, give_luna_treat,
                    play_with_luna, ignore_luna).

gemini_client.py  - Connects to mcp_server.py as an MCP client over stdio,
                    translates the tool schemas into Gemini function
                    declarations, and runs the call-tool / feed-result loop
                    until Gemini reaches a verdict. Returns the verdict AND
                    the full trace of what was checked.

app.py            - Streamlit dashboard. Shows live stats, lets you manually
                    poke Luna (feed/walk/play/ignore), and lets you ask the
                    agent a question and watch it investigate before it
                    answers.
```

## Setup

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

export GOOGLE_API_KEY="your-gemini-api-key"

./venv/bin/streamlit run app.py
```

## Why this shape

The interesting part isn't that an LLM can answer "why is my dog acting
weird." It's that this one has to check `last_meal`, `treats_today`,
`energy`, and `boredom` before it's allowed to say anything, and you can
watch it do that, tool call by tool call, in the dashboard. Remove the
trace and this is just a chatbot wearing a dog collar. The trace is the
point.

No fake precision either — the agent gives you the numbers it found and a
plain-English read, not a fabricated "82.735% confidence" score. If the
evidence is ambiguous, it says so.
