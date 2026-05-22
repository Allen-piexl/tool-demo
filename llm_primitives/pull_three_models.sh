#!/usr/bin/env bash
set -e
curl http://localhost:11431/api/pull -d '{"name":"qwen3:8b"}'
curl http://localhost:11432/api/pull -d '{"name":"qwen3:8b"}'
curl http://localhost:11433/api/pull -d '{"name":"qwen3:8b"}'
