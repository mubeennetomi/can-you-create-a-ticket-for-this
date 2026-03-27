"""Jira client: creates tickets and uploads attachments."""

from pathlib import Path

from jira import JIRA
from jira.exceptions import JIRAError


class JiraCreator:
    def __init__(self, server: str, email: str, api_token: str, project_key: str):
        self.project_key = project_key
        self.jira = JIRA(server=server, basic_auth=(email, api_token))
        self._valid_issue_types = None
        self._valid_components = None

    def _get_valid_issue_types(self) -> list[str]:
        if self._valid_issue_types is None:
            try:
                meta = self.jira.createmeta(projectKeys=self.project_key, expand="projects.issuetypes")
                types = []
                for proj in meta.get("projects", []):
                    for it in proj.get("issuetypes", []):
                        types.append(it["name"])
                self._valid_issue_types = types or ["Story", "Bug", "Task"]
            except Exception:
                self._valid_issue_types = ["Story", "Bug", "Task"]
        return self._valid_issue_types

    def _get_valid_components(self) -> set[str]:
        if self._valid_components is None:
            try:
                self._valid_components = {c.name for c in self.jira.project_components(self.project_key)}
            except Exception:
                self._valid_components = set()
        return self._valid_components

    def build_fields(self, ticket: dict, field_configs: list) -> dict:
        """Build Jira API fields dict from ticket data using field config."""
        fields = {"project": {"key": self.project_key}}

        for fc in field_configs:
            key = fc["key"]
            jira_field = fc["jira_field"]
            jira_type = fc["jira_type"]
            val = ticket.get(key)

            # Tags fields may come as list or comma-string
            if fc["type"] == "tags":
                if isinstance(val, str):
                    val = [v.strip() for v in val.split(",") if v.strip()]
                elif not isinstance(val, list):
                    val = []

            if not val and val != 0:
                continue

            if jira_type == "string":
                fields[jira_field] = val

            elif jira_type == "object_name":
                # Special handling: validate issue type
                if jira_field == "issuetype":
                    valid = self._get_valid_issue_types()
                    if val not in valid:
                        val = next((t for t in ["Story", "Task", "Bug"] if t in valid), valid[0])
                fields[jira_field] = {"name": val}

            elif jira_type == "object_value":
                fields[jira_field] = {"value": val}

            elif jira_type == "array_string":
                if isinstance(val, list) and val:
                    fields[jira_field] = [str(v).replace(" ", "_") for v in val]

            elif jira_type == "array_object_name":
                if isinstance(val, list) and val:
                    valid_comps = self._get_valid_components()
                    matched = [{"name": c} for c in val if not valid_comps or c in valid_comps]
                    if matched:
                        fields[jira_field] = matched

        return fields

    def create_ticket(self, ticket: dict, attachment_paths: list[str] | None = None,
                      field_configs: list | None = None) -> dict:
        if field_configs:
            fields = self.build_fields(ticket, field_configs)
        else:
            # Fallback: minimal fields
            fields = {
                "project": {"key": self.project_key},
                "summary": ticket.get("summary", ""),
                "description": ticket.get("description", ""),
                "issuetype": {"name": "Task"},
            }

        try:
            issue = self.jira.create_issue(fields=fields)
        except JIRAError as e:
            detail = e.text or ""
            try:
                detail = e.response.text
            except Exception:
                pass
            # Retry without priority if that caused the error
            if "priority" in fields and "priority" in detail.lower():
                del fields["priority"]
                try:
                    issue = self.jira.create_issue(fields=fields)
                except JIRAError as e2:
                    d2 = e2.text or ""
                    try:
                        d2 = e2.response.text
                    except Exception:
                        pass
                    raise RuntimeError(f"Jira error: {d2}") from e2
            else:
                raise RuntimeError(f"Jira error: {detail}") from e

        issue_key = issue.key
        issue_url = f"{self.jira.server_url}/browse/{issue_key}"

        if attachment_paths:
            for path in attachment_paths:
                p = Path(path)
                if p.exists():
                    try:
                        self.jira.add_attachment(issue=issue_key, attachment=str(p), filename=p.name)
                    except JIRAError as e:
                        print(f"Warning: could not attach {p.name}: {e.text}")

        return {"key": issue_key, "url": issue_url, "id": issue.id}

    def get_projects(self) -> list[dict]:
        projects = self.jira.projects()
        return [{"key": p.key, "name": p.name} for p in sorted(projects, key=lambda x: x.key)]
