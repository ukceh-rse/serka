## v0.1.0b0 (2026-05-29)


- chore: remove stale files
- chore(all): merge rc-alpha
- fix(feedback): ensures feedback is logged with additional details
- AI-Assisted: Claude Code
Reviewed-by: mpc
- feat(ui): clean citation source display in ai summary
- AI-Assisted: Claude Code
Reviewed-by: mpc
- fix(ui): fix template chat page build issue
- AI-Assisted: Claude Code
Reviewed-by: mpc
- feat(ui): ux improvemnets, icons, ai summary
- AI-Assisted: Claude Code
Reviewed-by: mpc
- fix(mcp logger): singleton for mcp and logger connectors
- AI-Assisted: Claude Code
Reviewed-by: mcp
- feat(ui): encode url params for link sharing
- AI-Assisted: Claude Code
Reviewed-by: mpc
- feat: add privacy policy notice
- AI-Assisted: Claude Code
Reviewed-by: mpc
- Geocoding (#61)
- * Added geocoding tool to mcp server
- * Extracted bounding box data from EIDC
- * Tweaked boundary attribute names
- * Updated RAG response to handle LLM tooling
- * Corrected filename in setup aws setup script
- * Added embedding model to deployed .env
- * Enabled geospatial filtering on mcp search

## v0.1.0a1 (2026-05-26)


- feat(ui): add react based ui
- ui using, react, zustrand and material ui
- AI-Assisted: Claude Code
Reviewed-by: mpc
- style(logo): shrinks logo
- style(ui): update to new brand
- Adds new logo, color pallete, and other UI enhancments (search suggestions, tooltips etc.)
- AI-Assisted: Claude Code
Reviewed-by: mpc
- perf(ingestion): batch and clean neo4j ingestion
- AI-Assisted: Claude Code
Reviewed-by: mpc
- Revert "perf(graph): add uri/doc_id indexes and fix label-less MATCH in relation writes"
- This reverts commit 58e644d40c40ee4c70abd36da9a5b9fada591302.
- perf(graph): add uri/doc_id indexes and fix label-less MATCH in relation writes
- feat(search): add hybrid search functionality
- AI-Assisted: Claude Code
Reviewed-by: mpc
- refactor(query): move semantic search fully to mcp server
- AI-Assisted: Claude Code
Reviewed-by: mpc
- feat(mcp): add cross-encoder reranking
- AI-Assisted: Claude Code
Reviewed-by: mpc
- docs(readme): add contribution guidelines
- chore(commitizen): add commitizen with convential commits and AI labelling
- AI-Assisted: Claude Code
Reviewed-by: mpc

## v0.1.0-alpha.0 (2026-05-05)


- Increased vm storage size
- Added logging output to ingestion and cleaned progress bars
- Added API versioning
- Added example env file
- Removed dev compose and updated documentation for dev deployment
- Ensure persistence of data and feedback logs in deployment environment
- Removed chroma dependencies
- Added health check
- Updated documentation for tearing down ec2 instance
- Increased default ec2 storage size
- Removed env file from container build
- Removed uneeded mongo container and fixed environment config
- Updated settings and environment options
- prevent alb teardown
- Added checks on data import for non-prose documents
- Cleaned compose files to use env vars
- Merged lock file
- Removed old mcp file and unnecessary warm up call
- Removed old rag method
- Removed Ollama support, Bedrock only
- Removed all Ollama provider branches, OllamaNodeEmbedder,
HypotheticalDocumentEmbedder, and associated HYDE prompts. Pipelines
now use Bedrock embedders and generators directly. Removed ollama
packages from dependencies.
- Migrated configuration to pydantic-settings
- Replaced YAML config files and scattered os.getenv calls with a single
Settings class using pydantic-settings. Removed config.yml and
config-podman.yml. Container compose now sets topology via environment
variables rather than mounting a config file.
- Added test mode with mock dependencies and unit tests
- Added mock implementations of DAO, FeedbackLogger and stream function
that are wired in via dependency_overrides when TEST_MODE is set.
Added basic unit tests for all API endpoints using FastAPI TestClient.
- Removed unused graph router and RAG endpoints from query router
- Added additional tools and search functionality to MCP server
- Fixed bug in data import causing crash on missing values
- Switched to AGUI adapter and updated UI
- Added experimental pydantic AI integration
- sso config for development
- Added ALB to terraform deployment
- Update outputs to display ID instead of public IP
- Updated instructions for connecting to web portal over ssm
- Re-ordered resource creation
- Added link to dpeloyment instructions
- Updated deployment instructions
- Modified terraform script for ssm access
- Enabled geospatial filtering on mcp search
- Added embedding model to deployed .env
- Corrected filename in setup aws setup script
- Updated RAG response to handle LLM tooling
- Tweaked boundary attribute names
- Extracted bounding box data from EIDC
- Added geocoding tool to mcp server
- MCP Integration (#60)
- * Added basic mcp server and agentic llm example
- * Containerised mcp server
- * Swapped rag pipeline for agenitc approach
- * Corrected podman deployment configuration
- * Initial hookup of mcp server to neo4j graph
- * Added semantic search as mcp tool
- * Added mcp methods for retrieving resources and non-dataset items from db
- * Fixed bug in formatting data for LLM
- Bedrock integration (#59)
- * Added bedrock example
- * Swapped out ollama for bedrock generator
- * Added bedrock integration
- * Fixed configuration to allow swapping between ollama and bedrock
- * Added outline for terraform setup
- * Setup ssh access
- * Added podman setup script
- * Created AWS podman compose config
- * Updated aws ports
- * Configured serka for automatic deployment to ec2
- * Setup init script to run containers as non-privelaged user'
- * Generated random user/pass for neo4j in aws setup script
- * Reverted to default neo4j username
- * Added bedrock test script
- * Added haystack bedrock test script
- * Added default aws region
- * Corrected default region env var
- * Removed secret handling from bedrock node embedder
- * Exposed neo4j port for aws deployment
- * Picking up correct neo4j credentials
- * Cleaned ec2 setup script
- * Moved notebook
- * Added readme for terraform setup
- * Cleaned tf vars output
- Podman deployment (#57)
- * Created podman compose file for scicom deployment
- * Updated README
- * Added ingestion script
- * Addeed compose profiles and standardised .yml filenames where possible
- * Fixed type in script
- * Updated readme
- Added consent tick box (#54)
- :sparkles: HyDE and Legilo Integration (#52)
- * initial legilo fetcher for graph pipeline
- * Moved to EIDC JSON dataset retrieval
- * Removed chromadb entirely
- * Added legilo scraping to knowledge graph
- * Tweaked retrieval to not give any textchunks that don't match query
- * Added HyDE implementation
- Knowledge graph (#49)
- * Knowledge graph implemented in neo4j
* RAG extracts semantically relevant nodes and their links
- Increased font size in details and made area scrollable (#43)
- :sparkles: Streaming generative response (#42)
- * Added basic streaming of rag responses
- * Cleaned streaming output in UI
- :sparkles: Adds privacy notice (#39)
- * Added privacy notice
- * Typos
- :sparkles: Group results by source document and UI branding (#38)
- * Groups semantic query results
- * UI shows details of groupby results
- * Added animation to show/hide details
- * Added UKCEH branding and styles
- * Tweaked styles
- :sparkles: Legilo parser (#37)
- * Created converter for Legilo
- * Configured authentication for legilo scraping
- * Added legilo crawler task
- * refactored routers into seperate files
- * fixed unit tests
- :sparkles: Pydantic API schema (#36)
- * Created PipelineBuilder and additional pydantic models
- * Added pydantic model for all API responses
- * Scarping endpoint now accepts list of urls in request body
- :sparkles: Job queue (#33)
- * Implements basic job queue
- * Moved to fastapi BackgroundTasks for job queue
- * Tightened pydantic model
- :sparkles: Added feedback database (#32)
- * Initial feedback database added
- * Hooked UI up to feedback endpoint
- * Added mongo data directory to gitignore
- :bug: cleaned app configuration #30
- Created pydantic model for configuration
- :sparkles: Unified embeddings (#29)
- * Unified embedding converter
- * Added unified metadata list to config
- :bug: Custom document source descriptions (#28)
- * Dynamically load document source descriptions into prompt
- * Moved collection description injection to prompt builder
- :sparkles: UI feedback changes
- * cleaned ui and added feedback components
- * Cleaned apline initialization
- * Updated rag default model
- :sparkles: adds RAG support (#21)
- * initial rag pipeline implementation
- * added rag output to ui with md rendering
- :sparkles: HTML file ingestion support (#19)
- * converter for html files
- * exposes html converter through api
- * ui options for different collections
- 🐛 allows for running without GPU support (#14)
- UI (#15)
- :sparkles: implements a minimal ui for semantic search
- adds custom haystack converter for EIDC data
- Switched model pull shell script to make use of yaml config
- adds semantic search and implements dao pattern
- exposes data import pipeline to api
- creates a basic fetcher for eidc metadata
- Merge pull request #6 from ukceh-rse/docker
- Docker
- Added configuration for ollama and chromadb containers
- Added ollama service to docker compose and default .env
- Dockerised API and created initial docker compose
- Merge pull request #2 from ukceh-rse/bootstrap
- Setup project files and tools
- Setup project files and tools
- Initial commit
