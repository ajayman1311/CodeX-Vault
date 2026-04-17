# CodeX-Vault
CodeX Vault: Technical Analysis and Briefing
--------------------------------------------------------------------------------
Executive Summary

The CodeX Vault is a high-performance, private cloud storage solution engineered for local network environments. Built on a Flask-based backend with a modern "Glassmorphism" frontend, the system distinguishes itself from traditional uploaders through its use of Chunk-based Sequential Uploading and Persistent Session Management. These core technologies allow the system to handle multi-gigabyte files with zero server overhead and extreme resilience against network fluctuations, server crashes, and power failures. The system is designed to provide a "Google Drive-like" experience within a private, highly scalable infrastructure.
--------------------------------------------------------------------------------
Core Technical Features and Value Propositions
The CodeX Vault architecture prioritizes data integrity and system efficiency through several intelligent subsystems:
Persistent Auto-Resume (Handshake Logic)
The system utilizes a unique "Handshake" protocol to ensure upload continuity.
Identification: Files are identified via a unique hash derived from the file name and size.
Verification: Before transmission, the client performs a Handshake with the server to identify existing chunks.
Efficiency: The system skips previously uploaded data, allowing sessions to resume from the exact point of failure even after a server restart or browser refresh.
Intelligent Cleanup System
To manage storage and prevent "bloat" from incomplete operations, the backend includes a Smart Cleanup utility:
Differentiation: It distinguishes between active, in-progress uploads and abandoned data.
Automation: Temporary data older than 24 hours is automatically purged, while current uploads are preserved.
Real-Time Network Sensing
The frontend maintains constant telemetry on connection quality:
Monitoring: The system tracks latency and response times for every individual chunk.
Alerting: If performance drops below a specific threshold, a "Slow Network Warning" is triggered to inform the user in real-time.
--------------------------------------------------------------------------------
Technology Stack
--------------------------------------------------------------------------------
The system utilizes a modern, multi-layered stack designed for production-grade stability and responsive user interaction.
Layer



| Technology | Purpose | Purpose |
| Backend | Python / Flask | Core logic, routing, and file handling. |
| Server | Waitress | Production-grade, multi-threaded request handling. |
| Database | JSON (Flat-file) | Lightweight management of configurations. |
| Frontend | HTML5, CSS3, JavaScript (ES6+) | UI rendering and client-side chunking logic. |
| Security | Werkzeug Utilities | Filename sanitization and session authentication. |

--------------------------------------------------------------------------------
System Architecture and Workflow
--------------------------------------------------------------------------------
The operational lifecycle of the CodeX Vault is divided into three distinct phases to ensure security and reliability.

Phase 1: Authentication and Access

Access is governed by a dual-key system:


Vault Key: The primary password required for access.

Protection ID: A secondary recovery key used specifically to reset security settings.


Phase 2: The Upload Lifecycle (Chunking)

Slicing: The client-side logic slices files into 2MB binary chunks.

Sync Check: The client calls the /check_progress route to retrieve a list of already uploaded indices.

Transmission: Chunks are transmitted sequentially via POST requests.

Finalization: Upon verification of all chunks, the /assemble route merges them into a single file. A unique timestamp prefix is added to prevent filename collisions.


Phase 3: Disaster Recovery and Failure Handling

The system is built to be "Stateful," meaning it remembers its progress regardless of external interruptions:

Connectivity Issues: If the internet is cut, the JavaScript loop enters a "Retry State," attempting reconnection every 5 seconds.

Server Failures: Because chunks are saved to the disk immediately upon receipt, a server crash does not result in data loss. The browser resumes pushing the next chunk once the server returns online.


--------------------------------------------------------------------------------
Security and Operational Protocols
--------------------------------------------------------------------------------
CodeX Vault implements several layers of protection to secure the local storage environment:

Filename Sanitization: The system uses secure_filename to strip malicious characters from all uploaded files.

Directory Isolation: Files are stored in a dedicated vault_files directory that lacks a direct public URL, preventing unauthorized external access.

Thread Isolation: The Waitress server is configured with 12 dedicated threads. This ensures that high-volume uploads by one user do not block access or degrade performance for other users.
--------------------------------------------------------------------------------
Deployment Specifications
The system is designed for rapid deployment in both corporate and personal environments.
Dependencies: Requires flask and waitress.
Execution: Launched via python app.py.
Access Points:
Local: http://localhost:5000
Network: http://[Your-IP]:5000
--------------------------------------------------------------------------------
Conclusion
--------------------------------------------------------------------------------
The CodeX Vault represents a shift from simple storage scripts to a comprehensive Stateful Cloud Application. By integrating client-side chunking with persistent server-side logic and a "Frozen Blue" Glassmorphism UI, it offers a resilient and professional-grade file management solution tailored for private network deployment.

