# GitHub Action

Use rulegraph directly in your GitHub Actions workflow:

```yaml
- name: rulegraph
  uses: sandeep-alluru/rulegraph@v0.1.0
  with:
    # TODO: add action inputs
    fail-on-error: "true"
```

Or use the CLI directly:

```yaml
- name: Install rulegraph
  run: pip install rulegraph

- name: Run rulegraph
  run: rulegraph --help
```
