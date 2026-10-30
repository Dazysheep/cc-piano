export class McpProjectBinding {
    pinned = null;
    get project() {
        return this.pinned;
    }
    clear() {
        this.pinned = null;
    }
    pin(requested, projects, current) {
        const candidate = requested === "current"
            ? current
            : projects.find((project) => project.id === requested || project.path === requested) ?? null;
        if (!candidate)
            throw new Error(`Unknown LLM Wiki project: ${requested}`);
        this.pinned = candidate;
        return candidate;
    }
    resolve(requested) {
        if (!this.pinned)
            return requested ?? "current";
        if (requested &&
            requested !== "current" &&
            requested !== this.pinned.id &&
            requested !== this.pinned.path) {
            throw new Error(`This MCP session is pinned to ${this.pinned.name} (${this.pinned.id}); ` +
                `project override ${requested} was rejected. Call llm_wiki_set_project to change scope.`);
        }
        return this.pinned.id;
    }
}
export function withActiveProject(text, project, requestedId) {
    const scope = project
        ? `${project.name} (${project.id})`
        : requestedId;
    return `[activeProject: ${scope}]\n\n${text}`;
}
