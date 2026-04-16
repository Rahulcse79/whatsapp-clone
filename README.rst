.. raw:: html

   <div align="center">

   <h1>💬 WhatsApp Clone</h1>

   <p><strong>A production-grade, real-time messaging platform built to handle 4,000+ concurrent users</strong></p>

   <p>
     <img src="https://img.shields.io/badge/Status-In%20Development-yellow?style=for-the-badge" alt="Status">
     <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
     <img src="https://img.shields.io/badge/Users-4000%2B%20Concurrent-blue?style=for-the-badge" alt="Users">
     <img src="https://img.shields.io/badge/PRs-Welcome-brightgreen?style=for-the-badge" alt="PRs">
   </p>

   <p><em>Real-time chat · End-to-end encryption · Media sharing · Presence & receipts · Built for scale</em></p>

   <br>
   <img src="docs/images/home.png" alt="WhatsApp Clone Server Running" width="700">
   <br><br>

   <hr>
   </div>

.. contents:: 📑 Table of Contents
   :depth: 2
   :local:

----

🚀 Project Vision
==================

This isn't just another chat app — it's an ambitious effort to build a
**WhatsApp-grade messaging system** from the ground up, engineered for
**real-world scale, security, and reliability**.

The goal is to deliver every core experience users expect from a modern
messaging platform:

+-------------------------------+---------------------------------------+
| Feature                       | Description                           |
+===============================+=======================================+
| 💬 Real-time Messaging        | Instant 1:1 and group conversations   |
+-------------------------------+---------------------------------------+
| ✅ Delivery & Read Receipts   | Sent → Delivered → Read status        |
+-------------------------------+---------------------------------------+
| 🟢 Presence & Typing          | Online/offline, last seen, typing...  |
+-------------------------------+---------------------------------------+
| 📎 Media & File Sharing       | Images, videos, docs, voice notes     |
+-------------------------------+---------------------------------------+
| 🔔 Push Notifications         | Instant alerts for offline users      |
+-------------------------------+---------------------------------------+
| 🔐 End-to-End Encryption      | Progressive E2EE rollout              |
+-------------------------------+---------------------------------------+
| 📱 Multi-device Sync          | Seamless cross-device experience      |
+-------------------------------+---------------------------------------+

----

📊 Current Status
==================

.. raw:: html

   <table>
     <tr>
       <td>🏗️ <strong>Phase</strong></td>
       <td>Foundation & Architecture Setup</td>
     </tr>
     <tr>
       <td>🎯 <strong>Focus</strong></td>
       <td>Backend-first: strong foundations before frontend polish</td>
     </tr>
     <tr>
       <td>📈 <strong>Target</strong></td>
       <td>4,000+ concurrent users with sub-100ms message latency</td>
     </tr>
   </table>

----

🎯 Scale & Performance Targets
================================

This system is being built to meet **production-grade benchmarks** from day one:

- **4,000+ concurrent users** with stable, predictable latency
- **Sub-100ms** message delivery for online recipients
- **Horizontal scalability** — add nodes, not limits
- **99.9% uptime** target with graceful degradation
- **Zero message loss** via durable persistence and acknowledgements
- **Full observability** — metrics, distributed tracing, structured logs

----

⚡ Core Features
==================

🔐 Authentication & Security
-----------------------------

- Secure sign-up/login with session management
- Token-based auth (JWT / OAuth2 ready)
- Rate limiting and brute-force protection
- Progressive end-to-end encryption

💬 Messaging Engine
--------------------

- Real-time WebSocket-powered messaging
- 1:1 private chats and group conversations
- Full message history with pagination and search
- Message editing and deletion
- Delivery states: **Sent → Delivered → Read**

👤 Presence & Status
---------------------

- Real-time online/offline detection
- "Last seen" timestamps
- Live typing indicators
- Custom status messages

📎 Media & Files
-----------------

- Image, video, document, and voice note uploads
- Secure object storage with signed URLs
- Thumbnail generation and compression
- File size limits and content validation

🔔 Notifications
------------------

- Push notifications for offline users
- In-app notification badges
- Notification preferences per chat
- Mute and Do Not Disturb support

🛡️ Moderation & Controls
--------------------------

- Report and block users
- Admin controls for group chats
- Content filtering capabilities
- Audit logging for sensitive actions

----

🏗️ High-Level Architecture
============================

.. code-block:: text

   ┌─────────────┐     ┌─────────────────────────────────────┐
   │   Clients   │────▶│           API Gateway                │
   │ (Web/Mobile)│     │  Auth · Rate Limit · Load Balance    │
   └─────────────┘     └──────────┬──────────────┬────────────┘
                                  │              │
                    ┌─────────────▼──┐   ┌───────▼──────────┐
                    │  Realtime       │   │  REST API        │
                    │  Messaging      │   │  Service         │
                    │  (WebSockets)   │   │  (HTTP)          │
                    └───────┬────────┘   └───────┬──────────┘
                            │                    │
              ┌─────────────▼────────────────────▼──────────┐
              │              Message Broker                  │
              │         (Event Queue / Pub-Sub)              │
              └──┬──────────┬───────────┬──────────┬────────┘
                 │          │           │          │
          ┌──────▼───┐ ┌───▼────┐ ┌────▼───┐ ┌───▼────────┐
          │ Message   │ │ Media  │ │Presence│ │Notification│
          │ Store     │ │Service │ │Service │ │  Service   │
          │ (DB)      │ │(S3/Obj)│ │(Redis) │ │  (Push)    │
          └──────────┘ └────────┘ └────────┘ └────────────┘

**Component Responsibilities:**

+---------------------+--------------------------------------------------+
| Component           | Role                                             |
+=====================+==================================================+
| API Gateway         | Request routing, auth, rate limiting, TLS         |
+---------------------+--------------------------------------------------+
| Realtime Service    | WebSocket lifecycle, message fan-out, sessions    |
+---------------------+--------------------------------------------------+
| REST API            | CRUD operations, user management, search          |
+---------------------+--------------------------------------------------+
| Message Broker      | Async event delivery, decoupling, replay          |
+---------------------+--------------------------------------------------+
| Message Store       | Durable chat persistence, history, indexing        |
+---------------------+--------------------------------------------------+
| Media Service       | Upload pipeline, storage, thumbnails, validation  |
+---------------------+--------------------------------------------------+
| Presence Service    | Online state, typing events, last-seen tracking   |
+---------------------+--------------------------------------------------+
| Notification Service| Push delivery, badge counts, preference routing   |
+---------------------+--------------------------------------------------+
| Monitoring Stack    | Prometheus metrics, Grafana dashboards, alerting  |
+---------------------+--------------------------------------------------+

----

🛠️ Tech Stack (Planned)
=========================

+---------------+------------------------------------------------------+
| Layer         | Technologies                                         |
+===============+======================================================+
| Backend       | Python · Rust · Async frameworks                     |
+---------------+------------------------------------------------------+
| Realtime      | WebSockets · Event-driven architecture               |
+---------------+------------------------------------------------------+
| Database      | PostgreSQL · Redis · Object Storage                  |
+---------------+------------------------------------------------------+
| Messaging     | Message queue / Pub-Sub broker                       |
+---------------+------------------------------------------------------+
| Infrastructure| Docker · CI/CD · Prometheus · Grafana                |
+---------------+------------------------------------------------------+
| Security      | TLS · JWT · E2EE · OWASP best practices             |
+---------------+------------------------------------------------------+

----

🗺️ Roadmap
============

**Phase 1 — Foundation** 🏗️
-----------------------------

- Define data models, auth flow, and core chat APIs
- Set up local development environment and CI pipeline
- Add base observability: structured logging, health checks
- Establish coding standards and contribution guidelines

**Phase 2 — Realtime Messaging MVP** 💬
-----------------------------------------

- Implement WebSocket-based messaging layer
- Build 1:1 chat and group conversations
- Add message persistence with delivery acknowledgements
- Basic user profiles and contact management

**Phase 3 — WhatsApp-like Experience** ✨
------------------------------------------

- Presence indicators: online, offline, last seen
- Live typing indicators and read receipts
- Media/file sharing pipeline with previews
- Push notifications for offline users
- Multi-device message synchronization

**Phase 4 — Production Hardening** 🔒
---------------------------------------

- Load testing and benchmarking for 4,000+ concurrent users
- Autoscaling strategy and queue optimization
- End-to-end encryption rollout
- Security audit, penetration testing
- Disaster recovery and backup/restore drills
- Documentation and deployment playbooks

----

📐 Non-Functional Priorities
==============================

.. raw:: html

   <table>
     <tr>
       <td>⚡ <strong>Performance</strong></td>
       <td>Low latency message delivery under heavy load</td>
     </tr>
     <tr>
       <td>🛡️ <strong>Reliability</strong></td>
       <td>Graceful degradation, retries, zero message loss</td>
     </tr>
     <tr>
       <td>🔐 <strong>Security</strong></td>
       <td>Encryption at rest & transit, secrets management, OWASP compliance</td>
     </tr>
     <tr>
       <td>🧩 <strong>Maintainability</strong></td>
       <td>Modular architecture, comprehensive tests, clean interfaces</td>
     </tr>
     <tr>
       <td>📊 <strong>Observability</strong></td>
       <td>Metrics, distributed tracing, structured logging, alerting</td>
     </tr>
     <tr>
       <td>📈 <strong>Scalability</strong></td>
       <td>Horizontal scaling, stateless services, partitioned data</td>
     </tr>
   </table>

----

🤝 Contributing
================

Contributions are welcome and encouraged! Here's how to get involved:

1. **Fork** the repository
2. **Create** a feature branch: ``git checkout -b feature/amazing-feature``
3. **Commit** your changes: ``git commit -m 'Add amazing feature'``
4. **Push** to the branch: ``git push origin feature/amazing-feature``
5. **Open** a Pull Request

Please open an issue first to discuss significant changes before submitting
large pull requests.

----

👤 Author
==========

**Rahul Singh**

- GitHub: `@rahulsingh <https://github.com/rahulsingh>`_

----

📄 License
===========

This project is licensed under the **MIT License** — see the
`LICENSE <LICENSE>`_ file for details.

----

.. raw:: html

   <div align="center">
     <br>
     <strong>⭐ If you find this project interesting, consider giving it a star!</strong>
     <br><br>
     <em>Built with ❤️ by Rahul Singh</em>
   </div>
