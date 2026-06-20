# API & Code Conventions

> Architect/developer/qa read this for API contract + naming rules. This replaces the
> old `conventions.md` / `api-standards.md`. Replace `<!-- TODO -->`.

## API Response Format
<!-- TODO: success shape and error shape. Example:
Success: { "data": {}, "meta": {} }
Error:   { "errors": [{ "code", "message", "field" }], "meta": {} }
-->

## HTTP Status Policy
<!-- TODO: do business errors use 4xx/5xx, or always 200 with a code? State it clearly —
this is a common source of bugs. -->

## URL / Resource Naming
<!-- TODO: plural nouns, kebab-case, versioning scheme, max nesting depth. -->

## Naming Conventions
<!-- TODO: files, classes, interfaces, constants, db tables/columns. -->

## Validation
<!-- TODO: where input is validated (DTO/schema lib), strict mode, content-type rules. -->

## Documentation
<!-- TODO: is OpenAPI/Swagger mandatory? where does the spec live? -->
