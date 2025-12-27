# Prompt Management

Version control for prompts in production.

## Basic Usage

```python
# Fetch prompt from Langfuse
from langfuse import Langfuse

langfuse = Langfuse()

# Get latest version of security auditor prompt
prompt = langfuse.get_prompt("security_auditor", label="production")

# Use in LLM call
response = await llm.generate(
    messages=[
        {"role": "system", "content": prompt.compile()},
        {"role": "user", "content": user_input}
    ]
)

# Link prompt to trace
langfuse.trace(
    name="security_analysis",
    metadata={"prompt_version": prompt.version}
)
```

## Prompt Versioning in UI

```
security_auditor
├── v1 (Jan 15, 2025) - production
│   └── "You are a security auditor. Analyze code for..."
├── v2 (Jan 20, 2025) - staging
│   └── "You are an expert security auditor. Focus on..."
└── v3 (Jan 25, 2025) - draft
    └── "As a cybersecurity expert, thoroughly analyze..."
```

## Prompt Templates with Variables

```python
# Create prompt in Langfuse UI:
# "You are a {{role}}. Analyze the following {{content_type}}..."

# Fetch and compile with variables
prompt = langfuse.get_prompt("content_analyzer")
compiled = prompt.compile(
    role="security auditor",
    content_type="API endpoint"
)

# Result:
# "You are a security auditor. Analyze the following API endpoint..."
```

## A/B Testing Prompts

```python
# Test two prompt versions
prompt_v1 = langfuse.get_prompt("security_auditor", version=1)
prompt_v2 = langfuse.get_prompt("security_auditor", version=2)

# Run A/B test
import random

for test_input in test_dataset:
    prompt = random.choice([prompt_v1, prompt_v2])

    response = await llm.generate(
        messages=[
            {"role": "system", "content": prompt.compile()},
            {"role": "user", "content": test_input}
        ]
    )

    # Track which version was used
    langfuse.trace(
        name="ab_test",
        metadata={"prompt_version": prompt.version}
    )

# Compare in Langfuse UI:
# - Filter by prompt_version
# - Compare average scores
# - Analyze cost differences
```

## Prompt Labels

Use labels for environment-specific prompts:

```python
# Development
dev_prompt = langfuse.get_prompt("analyzer", label="dev")

# Staging
staging_prompt = langfuse.get_prompt("analyzer", label="staging")

# Production
prod_prompt = langfuse.get_prompt("analyzer", label="production")
```

## Best Practices

1. **Use prompt management** instead of hardcoded prompts
2. **Version all prompts** with meaningful descriptions
3. **Test in staging** before promoting to production
4. **Track prompt versions** in trace metadata
5. **Use variables** for reusable prompt templates
6. **A/B test** new prompts before full rollout
7. **Document changes** in version notes

## Migration from Hardcoded Prompts

```python
# Before (hardcoded)
system_prompt = "You are a security auditor. Analyze code for vulnerabilities..."

# After (Langfuse-managed)
prompt = langfuse.get_prompt("security_auditor", label="production")
system_prompt = prompt.compile()
```

## References

- [Langfuse Prompt Management](https://langfuse.com/docs/prompts)
- [Prompt Templates Guide](https://langfuse.com/docs/prompts/get-started)
- [A/B Testing Prompts](https://langfuse.com/docs/prompts/example-openai-functions)
