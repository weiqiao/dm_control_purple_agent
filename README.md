# DMC Purple Agent (Baseline)

This is a **baseline purple agent** built from the A2A agent template. It is intended to be
evaluated by the green DMC evaluator agent from `dmc-green-evaluator-template.zip`.

The agent implements a minimal DMC step protocol and outputs **random continuous actions**
within the provided action bounds.

## Project Structure

```
src/
├─ server.py      # Server setup and agent card configuration
├─ executor.py    # A2A request handling
├─ agent.py       # Your agent implementation goes here
└─ messenger.py   # A2A messaging utilities
tests/
└─ test_agent.py  # Agent tests
Dockerfile        # Docker configuration
pyproject.toml    # Python dependencies
.github/
└─ workflows/
   └─ test-and-publish.yml # CI workflow
```

## DMC Evaluator Protocol

The green evaluator will send JSON messages. Your agent should respond with a JSON string.

### Init message (optional)

```json
{
  "kind": "dmc_init",
  "task": "walker_walk",
  "seed": 0,
  "action_spec": {"shape": [6], "minimum": [-1, ...], "maximum": [1, ...]},
  "observation_spec": {"...": "..."}
}
```

This baseline agent replies with `{ "ok": true }` and stores the action spec for the current
conversation.

### Step message

```json
{
  "kind": "dmc_step",
  "task": "walker_walk",
  "episode": 0,
  "t": 0,
  "observation": {"...": "..."},
  "reward": 0.0,
  "discount": 1.0,
  "step_type": "StepType.FIRST",
  "action_spec": {"shape": [6], "minimum": [-1, ...], "maximum": [1, ...]}
}
```

Your agent must respond with:

```json
{ "action": [ ... ] }
```

The evaluator will clip actions to the declared bounds.

## Getting Started

1. **Create your repository** - Click "Use this template" to create your own repository from this template

2. **Implement your agent** - Add your agent logic to [`src/agent.py`](src/agent.py)

3. **Configure your agent card** - Fill in your agent's metadata (name, skills, description) in [`src/server.py`](src/server.py)

4. **Write your tests** - Add custom tests for your agent in [`tests/test_agent.py`](tests/test_agent.py)

For a concrete example of implementing an agent using this template, see this [draft PR](https://github.com/RDI-Foundation/agent-template/pull/8).

## Running Locally

```bash
# Install dependencies
uv sync

# Run the server
uv run src/server.py
```

## Running with Docker

```bash
# Build the image
docker build -t my-agent .

# Run the container
docker run -p 9009:9009 my-agent
```

## Testing

Run A2A conformance tests against your agent.

```bash
# Install test dependencies
uv sync --extra test

# Start your agent (uv or docker; see above)

# Run tests against your running agent URL
uv run pytest --agent-url http://localhost:9009
```

## Publishing

The repository includes a GitHub Actions workflow that automatically builds, tests, and publishes a Docker image of your agent to GitHub Container Registry.

If your agent needs API keys or other secrets, add them in Settings → Secrets and variables → Actions → Repository secrets. They'll be available as environment variables during CI tests.

- **Push to `main`** → publishes `latest` tag:
```
ghcr.io/<your-username>/<your-repo-name>:latest
```

- **Create a git tag** (e.g. `git tag v1.0.0 && git push origin v1.0.0`) → publishes version tags:
```
ghcr.io/<your-username>/<your-repo-name>:1.0.0
ghcr.io/<your-username>/<your-repo-name>:1
```

Once the workflow completes, find your Docker image in the Packages section (right sidebar of your repository). Configure the package visibility in package settings.

> **Note:** Organization repositories may need package write permissions enabled manually (Settings → Actions → General). Version tags must follow [semantic versioning](https://semver.org/) (e.g., `v1.0.0`).
