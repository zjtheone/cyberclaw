# Skill Creation Process

This guide covers the complete workflow for creating, editing, and packaging skills.

## Overview

Skill creation involves these steps:

1. **Understand** the skill with concrete examples
2. **Plan** reusable skill contents (scripts, references, assets)
3. **Initialize** the skill (run `init_skill.py`)
4. **Edit** the skill (implement resources and write SKILL.md)
5. **Package** the skill (run `package_skill.py`)
6. **Iterate** based on real usage

Follow these steps in order, skipping only if there is a clear reason why they are not applicable.

---

## Step 1: Understanding the Skill

Skip this step only when the skill's usage patterns are already clearly understood.

To create an effective skill, clearly understand concrete examples of how the skill will be used. This understanding can come from either direct user examples or generated examples that are validated with user feedback.

### Example Questions

For an image-editor skill:

- "What functionality should the image-editor skill support? Editing, rotating, anything else?"
- "Can you give some examples of how this skill would be used?"
- "I can imagine users asking for things like 'Remove the red-eye from this image' or 'Rotate this image'. Are there other ways you imagine this skill being used?"
- "What would a user say that should trigger this skill?"

**Tip:** To avoid overwhelming users, avoid asking too many questions in a single message. Start with the most important questions and follow up as needed.

**Completion criteria:** There is a clear sense of the functionality the skill should support.

---

## Step 2: Planning Reusable Contents

To turn concrete examples into an effective skill, analyze each example by:

1. Considering how to execute on the example from scratch
2. Identifying what scripts, references, and assets would be helpful when executing these workflows repeatedly

### Examples

**PDF Editor Skill**

For queries like "Help me rotate this PDF":

1. Rotating a PDF requires re-writing the same code each time
2. A `scripts/rotate_pdf.py` script would be helpful

**Frontend Builder Skill**

For queries like "Build me a todo app" or "Build me a dashboard":

1. Writing a frontend webapp requires the same boilerplate HTML/React each time
2. An `assets/hello-world/` template containing boilerplate files would be helpful

**BigQuery Skill**

For queries like "How many users have logged in today?":

1. Querying BigQuery requires re-discovering the table schemas and relationships each time
2. A `references/schema.md` file documenting the table schemas would be helpful

**Output:** Create a list of the reusable resources to include: scripts, references, and assets.

---

## Step 3: Initializing the Skill

Skip this step only if the skill being developed already exists, and iteration or packaging is needed.

When creating a new skill from scratch, always run the `init_skill.py` script. The script generates a new template skill directory that automatically includes everything a skill requires.

### Usage

```bash
scripts/init_skill.py <skill-name> --path <output-directory> [--resources scripts,references,assets] [--examples]
```

### Examples

```bash
scripts/init_skill.py my-skill --path skills/public
scripts/init_skill.py my-skill --path skills/public --resources scripts,references
scripts/init_skill.py my-skill --path skills/public --resources scripts --examples
```

### What the Script Does

- Creates the skill directory at the specified path
- Generates a SKILL.md template with proper frontmatter and TODO placeholders
- Optionally creates resource directories based on `--resources`
- Optionally adds example files when `--examples` is set

After initialization, customize the SKILL.md and add resources as needed. If you used `--examples`, replace or delete placeholder files.

---

## Step 4: Edit the Skill

When editing the (newly-generated or existing) skill, remember that the skill is being created for another instance of the agent to use. Include information that would be beneficial and non-obvious to the agent.

### Learn Design Patterns

Consult these helpful guides based on your skill's needs:

- **Multi-step processes**: See [workflows.md](workflows.md) for sequential workflows and conditional logic
- **Specific output formats or quality standards**: See [output-patterns.md](output-patterns.md) for template and example patterns

These files contain established best practices for effective skill design.

### Start with Reusable Contents

To begin implementation, start with the reusable resources identified above: `scripts/`, `references/`, and `assets/` files.

**Note:** This step may require user input. For example, when implementing a `brand-guidelines` skill, the user may need to provide brand assets or templates.

**Testing:** Added scripts must be tested by actually running them to ensure there are no bugs. If there are many similar scripts, only a representative sample needs to be tested.

If you used `--examples`, delete any placeholder files that are not needed for the skill. Only create resource directories that are actually required.

### Update SKILL.md

**Writing Guidelines:** Always use imperative/infinitive form.

#### Frontmatter

Write the YAML frontmatter with `name` and `description`:

- `name`: The skill name
- `description`: This is the primary triggering mechanism for your skill. Include both what the Skill does and specific triggers/contexts for when to use it.
  - Include all "when to use" information here - Not in the body. The body is only loaded after triggering, so "When to Use This Skill" sections in the body are not helpful to the agent.
  - Example description for a `docx` skill: "Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction. Use when the agent needs to work with professional documents (.docx files) for: (1) Creating new documents, (2) Modifying or editing content, (3) Working with tracked changes, (4) Adding comments, or any other document tasks"

Do not include any other fields in YAML frontmatter.

#### Body

Write instructions for using the skill and its bundled resources.

---

## Step 5: Packaging a Skill

Once development of the skill is complete, it must be packaged into a distributable `.skill` file. The packaging process automatically validates the skill first to ensure it meets all requirements:

```bash
scripts/package_skill.py <path/to/skill-folder>
```

Optional output directory specification:

```bash
scripts/package_skill.py <path/to/skill-folder> ./dist
```

### What the Packaging Script Does

1. **Validate** the skill automatically, checking:
   - YAML frontmatter format and required fields
   - Skill naming conventions and directory structure
   - Description completeness and quality
   - File organization and resource references

2. **Package** the skill if validation passes, creating a `.skill` file named after the skill (e.g., `my-skill.skill`) that includes all files and maintains the proper directory structure for distribution. The `.skill` file is a zip file with a `.skill` extension.

If validation fails, the script will report the errors and exit without creating a package. Fix any validation errors and run the packaging command again.

---

## Step 6: Iterate

After testing the skill, users may request improvements. Often this happens right after using the skill, with fresh context of how the skill performed.

### Iteration Workflow

1. Use the skill on real tasks
2. Notice struggles or inefficiencies
3. Identify how SKILL.md or bundled resources should be updated
4. Implement changes and test again

---

## Related References

- [Skill Design Principles](design-principles.md) - Core principles for effective skill design
- [Progressive Disclosure Patterns](progressive-disclosure.md) - Patterns for organizing skill content
- [Workflows](workflows.md) - Sequential workflows and conditional logic
- [Output Patterns](output-patterns.md) - Template and example patterns
