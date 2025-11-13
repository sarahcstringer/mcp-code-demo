# Code execution with MCP: separating context from computation

**TL;DR:** Traditional tool calling eats away at an agent's context window. All the tool definitions and every intermediate result pass through it. Code execution gives agents a "scratch pad" workspace to process data outside the context window. Combined with MCP's tool abstractions, this can significantly reduce token usage for data-heavy tasks.

Check out the [demo repository](https://github.com/sarahcstringer/mcp-code-demo) for two examples you can run.

---

I thought I understood MCP. [It took me a while](https://deatons.substack.com/p/learn-mcp-with-me-part-1-what-is), but I recognized that we need MCP as a standardized layer to best interact with external services. MCP gives LLMs structured access to APIs, providing a consistent interface instead of varying parameter names and request/response formats across different services.

Then I read Anthropic's post about [code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) and Cloudflare's piece on [Code Mode](https://blog.cloudflare.com/code-mode/), which talk about having LLMs write code to call MCP servers, and I got confused again.

Why are we having LLMs write code around MCP servers when we wrote MCP servers so that… LLMs **didn’t have to write code** to interact with APIs?

The piece that finally clicked: a key benefit of code execution is that it happens in an execution environment, not in the agent's context window.

MCP is still the standardization layer; generating Python wrappers for MCP tools makes them available as importable functions in the execution environment. Then, if the LLM has access to a bash tool that executes commands, it can write and execute entire scripts in its execution environment and only send the final answer back to context.

As an analogy: traditional tool calling requires you to show every single calculation on your final exam paper: all the messy scratch work, the raw data, the transformed versions, crossed-out mistakes. You run out of space fast, and the grader (the LLM) has to wade through all that noise to find the final answer. MCP + code execution is like giving you scratch paper to process data and perform operations outside the context window. Then you just record the final result on your exam paper.

## Context window vs. execution environment

The **context window** is the LLM's working memory. It's expensive (costs tokens), limited in size, and includes:

- System prompt  
- Conversation history  
- Tool descriptions  
- Tool results  
- The response being generated

The **execution environment** is where code actually runs. In development, it might be your laptop. In production, it's typically a sandboxed Docker container or VM with limited filesystem and network access. It's relatively cheap and can handle large data processing.

Modern agent frameworks like [Claude Code](https://www.anthropic.com/engineering/code-execution-with-mcp) and [Cloudflare Agents](https://blog.cloudflare.com/code-mode/) provide code execution environments built-in, but you can also achieve the same pattern by giving any LLM a bash tool that executes commands in your execution environment.

## The problem: your context window is getting bloated

Tool calling is great for letting LLMs use APIs and external tools, but once you have a production system with large datasets and hundreds of tools, it quickly runs into a major problem: **all the tool definitions and every intermediate result from every tool call has to pass through your context window.**

If you want to fetch 300 records, transform the data, and filter it with tools, all of the following must pass through context:

- The tool definitions  
- The raw data from the records  
- The transformed data  
- The filtered data

Each step consumes more of your expensive, limited window until you hit the limit or face substantial cost increases. Your agent also has to sort through all the results and its working memory is crowded with information that isn't actually relevant for its final response.

## The solution: code execution in an execution environment

Code execution gives agents a "scratch pad" workspace to process data outside the context window. It allows the agent to write code that calls MCP tools, process results locally in the execution environment, and only record the final result in context.

![Comparison diagram showing traditional tool calling with all operations in the context window versus code execution with a separate execution environment for processing](./mcp-code.png)

MCP still handles the "How do I call this API correctly?" problem by giving LLMs structured tools instead of making them write raw API calls that vary from API to API.

Code execution solves the "How do I process all this data without destroying my context window?" problem by giving the agent a workspace to process data outside the context window.

Beyond data processing, code execution unlocks capabilities that are challenging with traditional tool calling. Things like polling for results and waiting, retrying failed requests, maintaining state across multiple operations, saving intermediate results and returning back to them later, all become possible through code.

## Production safety: guardrails for code execution

Giving an LLM the ability to execute code is powerful, but requires guardrails. Three key practices:

**1\. Sandboxed execution:** Run code in isolated Docker containers or VMs, not your production environment. Limit filesystem and network access or use something like the [Cloudflare Sandbox SDK](https://developers.cloudflare.com/sandbox/) or [Daytona](https://www.daytona.io/) for runtime isolation.

**2\. Human approval for destructive actions:** Require approval for anything that costs money, modifies data, or communicates externally. For example, `read_channel_messages` might auto-approve, but `post_message_to_all_hands` should require review.

**3\. Thoughtful tool design:** Don't expose raw endpoints. Build high-level tools like `schedule_meeting` (checks availability \+ books room) instead of `list_users` / `list_events` / `create_event`. Prefer search-focused results (`search_contacts("Jane")`) over giant dumps (`list_all_contacts()`).

The [Anthropic article on writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) covers these design principles in depth.

## When to use each approach

Not every task needs code execution. Traditional tool calling works well for certain scenarios:

**Traditional tool calling works when:**

- Tool results are small (a few hundred tokens)
- You need one or two tool calls total
- No data processing required
- Results go directly to the user

**Code execution excels when:**

- Processing large datasets
- Making multiple related tool calls
- Filtering or transforming results
- Polling or waiting for completion
- Maintaining state across operations

## Limitations and trade-offs

Code execution isn't without its challenges:

**Model capability matters:** Code execution requires models with strong coding abilities. Not all LLMs write clean, correct code consistently. If your model struggles with code generation, the benefits diminish quickly. Test your chosen model's coding capabilities before committing to this pattern.

**Debugging is harder:** When a traditional tool call fails, you see exactly which tool was called and what it returned. When code execution fails, you need to debug the generated code itself—parsing errors, logic bugs, incorrect API usage. This adds complexity to your error handling and monitoring.

**Security surface area:** Executing LLM-generated code introduces risks beyond traditional tool calling. Even with sandboxing, you need to worry about resource exhaustion, unintended file system access, infinite loops, and malicious prompt injections that generate harmful code. The guardrails mentioned earlier are necessary but not sufficient—you need ongoing monitoring and careful tool design.

**Added latency:** Code execution requires the LLM to first generate code, then execute it, then process results. This adds a generation step that traditional tool calling skips. For simple queries where traditional tool calling would work fine, code execution may actually be slower.

**Complexity:** Your system needs to manage an execution environment, handle code execution errors gracefully, and potentially deal with environment setup and dependencies. Traditional tool calling has a simpler operational model.

Despite these trade-offs, for data-heavy tasks where token costs and context window limits are real constraints, code execution can provide significant practical benefits.

## The mental model shift

Agents are more than LLMs with tools. They're LLMs with tools and an execution environment.

The context window is for reasoning. The execution environment is for working.

When you structure agents this way, you get:

- Significant reduction in token usage (varies by task, but can be substantial for data-heavy operations)
- Natural patterns for polling and async operations
- Ability to process large datasets
- Stateful computation without context bloat
- More predictable results by executing deterministic code rather than tracking state in context

Code execution can improve reliability by reducing the need for the LLM to track state and aggregate data across multiple tool calls in context. By having the agent write deterministic scripts that run in the execution environment, you get more predictable and complete results.

**Note:** The effectiveness of this approach depends significantly on the model you use. Models with strong coding capabilities will write better, more efficient code. The token savings also vary based on your specific use case—tasks involving large datasets or many sequential operations see the most benefit.

MCP provides the standardized tools. Code execution provides the workspace to use them efficiently. Together, they enable agents that are both capable and cost-effective.

## Try it yourself

I created a [demo repository](https://github.com/sarahcstringer/mcp-code-demo) with two examples you can run and play around with:

1. **Traditional tool calling**: Shows how intermediate data fills the context window
2. **Code execution**: Shows how processing happens in the execution environment

Both examples include token usage metrics so you can compare the approaches.

**Note on token variability:** Token usage varies between runs, even with the same task and model. In my testing with this demo, I've seen the following results:

- **Traditional tool calling**: Typically 50,000-73,000 tokens
- **Code execution**: Typically 9,500-10,000 tokens
- **Token reduction**: 80-87% depending on the run

To run the examples:

```shell
# Clone this repo
git clone https://github.com/sarahcstringer/mcp-code-demo
cd mcp-code-demo

# Install dependencies
pip install -r requirements.txt

# Set up your Anthropic API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run the traditional tool calling example
python examples/traditional_tool_calling.py

# Generate MCP tool wrappers for the code execution example
python generate_wrappers.py

# Run the code execution example
python examples/code_execution.py
```

The examples use Anthropic's Claude Haiku 4 model with the Anthropic SDK, but the patterns work with any model provider.

## Next steps

- [Read the Anthropic post on code execution](https://www.anthropic.com/engineering/code-execution-with-mcp)  
- [Learn best practices for writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)  
- [Check out Cloudflare's Code Mode explanation](https://blog.cloudflare.com/code-mode/)  
- [Learn about MCP](https://modelcontextprotocol.io)

