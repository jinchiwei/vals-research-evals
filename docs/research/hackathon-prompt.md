# Official track prompt

Exact text supplied by Jin on 2026-11-14. This takes precedence over earlier paraphrases.

Build Your Own Eval
Overview
The goal of this track is to find a task that frontier models still get wrong, and turn it into a benchmark.

You will be judged on your benchmark’s:

Novelty - How creative is the benchmark
Execution - How well built is the benchmark
Difficulty - Can frontier models solve the tasks or do they struggle
Importance - How much impact would the benchmark have to the world at large
You will also be judged on clarity and presentation of results.

You will run it on Valkyrie, a distributed platform Vals AI uses to run agent benchmarks. Valkyrie is designed to allow easy remote execution of many benchmark tasks in parallel.

Setup
Claim your Claude and OpenAI API credits in Your credits to test your evaluation.
Claim your Modal credits for the sandboxes that run your evaluation tasks.
Install uv, then the Valkyrie CLI:
uv tool install valkyrie-cli
Run valkyrie login only if you haven't signed in, using the same account as this hackathon page. Then select your team's organization, hackathon-neuronetwork-b91c517178. An already signed-in session picks up the new org automatically.
valkyrie org use hackathon-neuronetwork-b91c517178
Then follow the Valkyrie quickstart from step 3 to run your first agent. Skip creating an organization.

Build tasks in the Harbor task format. Use the dataset commands to upload your dataset to Valkyrie and run it.
Example command:

valkyrie dataset push my-benchmark/my-dataset ./tasks --tag v1
valkyrie run start --agent claude_code-v1.0.0 \
  --dataset my-benchmark/my-dataset@v1 \
  --model anthropic/claude-sonnet-4-6 --provider modal \
  -s ANTHROPIC_API_KEY anthropic-api-key \
  --concurrency 1 --connect
Watch runs live in the terminal. Everyone on your team sees the same runs, datasets and task logs, and can use any agent a teammate installed.
valkyrie tui
Save your project below. Judges see it at demos on Sun 2 PM, and you can edit it until then.
For more information about Valkyrie, consult the documentation, run valkyrie --help, or ask your agent. The source code is publicly available here.

Harnesses Available
We have the following harnesses available to use out-of-the-box:

Claude Code
Codex
mini-SWE-agent
You can also add a custom harness to Valkyrie: https://docs.valkyrie.vals.ai/agents/package-an-agent

What you submit
Code and data: A GitHub repo with your tasks and a README that says how to run them. You can also upload the dataset to Valkyrie.
Writeup: How the benchmark works, at the top of the README. You should have a one paragraph overview at the start that is entirely human-written.
Results: How frontier models score on your benchmark. Put them in the README (graphs preferred alongside tables).
Traces or Examples (optional): Model rollouts, or the ID of your Valkyrie run. Showing a concrete failure mode the benchmark exposes goes a long way.
Other Tips
We recommend focusing on quality of samples, not quantity
Keep in mind your budget. Try small experiments before scaling up.
We recommend no public internet access for your agents (to avoid HuggingFace-esque disasters)
Look at your traces and rollouts in tandem with building the benchmark
You should be able to justify why you chose the harness you did
