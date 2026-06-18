# rulegraph — Session Anchor

**Research spec:** `../tech-research/14-Gaming/rules-grounded-gm-arbitration-via-symbolic-neural-hybrid/README.md`  
**One-liner:** Compile game rulebooks into queryable constraint engines (symbolic checker + LLM arbitrator)  
**Phase:** backlog  
**Stack:** Python, z3-solver, anthropic (Claude API)  

## Key decisions
<!-- fill in as decisions are made during build sessions -->

## Next step
Read the research spec, then design the rulebook → probabilistic rule graph parsing pipeline.

## MVP definition
- `pip install rulegraph` works
- Parses natural language rulebook → probabilistic rule graph (via LLM)
- z3-based symbolic checker for determinate rules (100% accuracy on clear cases)
- LLM arbitrator for genuinely ambiguous rules (with citations)
- API: `rulegraph.load(rulebook_text)`, `rulegraph.adjudicate(situation) → ruling + citation`
- Demo: load D&D 5e basic combat rules, adjudicate 3 test cases correctly
- README with the symbolic/neural hybrid architecture diagram
