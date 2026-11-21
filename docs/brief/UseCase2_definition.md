# Use Case 2: Corporate Crisis Manager

## Goal
Build a system of AI agents that helps **ACME**, a fictional consumer electronics company, assess and respond to an emerging crisis. The system uses company documents and new evidence to evaluate impacts, recommend actions and update a Crisis Management Report through an ongoing chat.

## The cycle
1. The user describes what happened and provides **text and images**, such as an article excerpt, a customer message or a screenshot of a social media post. Text and readable PDF files can be uploaded directly to the orchestrator chat. Screenshots can be included in a PDF. Direct image uploads may also be used where supported.
2. The system reviews the evidence and the ACME company files, then produces its first analysis and **Crisis Management Report v1**.
3. In the **same chat**, the user adds new information, attachments, actions taken by the company and observed results.
4. The system reviews the whole situation and produces **v2, v3…**, showing what changed and why. Earlier facts remain valid unless new evidence replaces or disproves them.
5. When the user decides to stop, the system records remaining risk, open actions and conditions for reopening the case.

## Required capabilities
- At least **two collaborating agents**. Their number, roles and capabilities are design choices.
- Use and cite the relevant company documents and incident sources. Distinguish current evidence from historical examples and informal notes.
- Separate confirmed facts, unconfirmed claims and disproved or potentially misleading claims. A screenshot does not by itself prove that a post is true.
- Assess **reputational, economic and legal/regulatory impacts**, identify stakeholders and propose priority actions with owners and timing.
- Express overall risk as **Low / Medium / High / Critical**. Define a qualitative assessment method and apply it consistently. Keep risk level separate from evidence strength.
- Distinguish proposed, approved and completed actions from actions whose results show that they worked.
- At each update, show previous and current risk, new evidence, changes to actions and reasons, even when the risk level stays the same.
- Produce a versioned report with: situation; evidence; risk and reasons; impacts; stakeholders; action plan; changes and open questions.
- Keep **one PDF for each report version**. Manual export is allowed; automatic generation and download may be included in the implementation.

## Implementation choices
The architecture and tools are open. Use the Orchestrate UI, workflows, custom code or integrations as appropriate. Bob may help with configuration, development and testing. No particular programming language, external service or scoring formula is required.

New incident information is supplied by the user; automatic web monitoring is optional. The system supports decisions and drafts responses. It does not carry out real recalls, regulatory notifications or public announcements.

## Company files
`UseCase2_knowledge_base.zip` contains company and product PDFs, internal emails, saved screenshots, support material and a warehouse export. ACME has handled routine customer issues but has no established company-wide crisis process. The system must bring together information from these different sources.
