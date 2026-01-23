# Supported Technologies

Claude Waypoints automatically detects your project's technology stack and configures compile/test commands accordingly.

## Profiles

| Profile | Detection | Compile Command | Test Command |
|---------|-----------|-----------------|--------------|
| Kotlin/Maven | `pom.xml` + `*.kt` | `mvn clean compile -q` | `mvn test -q` |
| Kotlin/Gradle | `build.gradle.kts` + `*.kt` | `./gradlew compileKotlin -q` | `./gradlew test -q` |
| TypeScript/npm | `package.json` + `tsconfig.json` | `npm run build` | `npm test` |
| TypeScript/pnpm | `package.json` + `tsconfig.json` + `pnpm-lock.yaml` | `pnpm run build` | `pnpm test` |
| JavaScript/npm | `package.json` + `*.js` | `npm run build` | `npm test` |
| JavaScript/pnpm | `package.json` + `pnpm-lock.yaml` + `*.js` | `pnpm run build` | `pnpm test` |
| Python/pytest | `pyproject.toml` + `*.py` | `python -m py_compile` | `python -m pytest -q` |
| Go | `go.mod` + `*.go` | `go build ./...` | `go test ./...` |
| Rust | `Cargo.toml` + `*.rs` | `cargo build` | `cargo test` |
| Java/Maven | `pom.xml` + `*.java` | `mvn clean compile -q` | `mvn test -q` |

## Override Auto-Detection

If auto-detection fails or you want to force a specific profile, create `~/.claude/wp-override.json`:

```json
{
  "activeProfile": "typescript-npm"
}
```

Valid profile names:
- `kotlin-maven`
- `kotlin-gradle`
- `typescript-npm`
- `typescript-pnpm`
- `javascript-npm`
- `javascript-pnpm`
- `python-pytest`
- `go`
- `rust`
- `java-maven`
