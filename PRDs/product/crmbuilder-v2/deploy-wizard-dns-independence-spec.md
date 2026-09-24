# Deploy wizard — deploying without DNS access, and a clearer wizard

| Field | Value |
|---|---|
| Title | Deploy wizard — deploying without DNS access, and a clearer wizard |
| Last Updated | 09-23-26 21:25 |
| Revision | 1.2 |
| Status | Approved for build by the product owner on 09-23-26 ("Let's try this and see if it is much better. Complete the specs, and let's build it"). |
| Source | Design discussion in session SES-432 (conversation CNV-401), 09-23-26. Requirements REQ-648..REQ-652, approved by DEC-1151. Built under PI-571 in PRJ-127. |
| Replaces | Nothing. Extends the version 2 deploy run (the original provisioning requirement, REQ-522) and the manual DNS mode added earlier the same day (REQ-642, DEC-1146). |

## 1. Why this exists

Three problems with the version 2 deploy wizard came out of real use.

1. **A client who controls their own Domain Name System (DNS) records cannot be deployed.** The wizard requires CRMBuilder's Cloudflare credential and writes the address record itself. Many clients' DNS is held by a volunteer, a registrar or a web host.
2. **A DNS problem wastes time and throws away the work.** The run repeats "not ready, retrying" with no explanation, gives up after ten minutes, and everything after the DNS step stops. The product owner watched this for over an hour, was never told there was a problem, and then had to start again.
3. **The wizard is hard to read.** It is a small window, with small grey hints and raw provider catalogue names, and it says little about what to do, how to check it worked, or what to do if it did not.

**Domain Name System (DNS):** the internet's directory that turns a web address such as `crm.example.org` into the numeric Internet Protocol (IP) address of a server.

## 2. What changes, in one paragraph

The operator enters the web address first. The wizard looks up who hosts DNS for that address. If CRMBuilder can edit it, the run creates the address record (Cloudflare DNS mode); if not, the run carries on and the client is given exact instructions (manual DNS). **The CRM is installed whether or not DNS is ready.** DNS is diagnosed, not just retried: every check says what was found, what it means, what to do and how to confirm it is fixed. A problem blocks only the steps that depend on it. Those steps become **open items** on the instance and are closed later by a **self-healing job on the server**, by the **Check DNS now** button, or by **Try again** with a corrected input. Nothing is thrown away, and nothing starts over.

## 3. Requirements

Five requirements, recorded in the store under topic "Multi-instance CRM connection, audit & inventory".

### 3.1 The operator chooses the address, and DNS is never a precondition of installing

- The wizard asks for the complete web address (for example `crm.clevelandbusinessmentors.org`) before anything else about the server.
- The wizard looks up the address's name servers and says in plain words who hosts DNS for it (Cloudflare, GoDaddy, Namecheap, and so on, or the name server names when the host is not recognised).
- **Cloudflare DNS mode** is offered when the address falls inside a Cloudflare zone that CRMBuilder's Cloudflare credential can edit **and** that zone is the one the internet actually uses. Otherwise the wizard uses **manual DNS**: the client creates the record, following instructions CRMBuilder prints.
- The DigitalOcean credential stays required. The Cloudflare credential becomes optional.
- The server is prepared and the CRM installed without a certificate before any DNS step. The installer runs in its plain web mode for the chosen address, so the CRM's site address is correct from the start.
- In Cloudflare DNS mode, an existing record for the address is **never overwritten**. A record already pointing at this server is accepted; any other existing A, AAAA or CNAME record for the name becomes an open item that says what is there.

### 3.2 DNS is diagnosed in plain words

One diagnostic serves the run, the Check DNS now button, the handover sheet and the self-healing job's status. It answers, in order:

1. **Which name servers answer for this domain?** If Cloudflare DNS mode created the record at a DNS host the internet does not use, say so. This will never fix itself.
2. **Does the record exist on those name servers?** If not: the record is missing, or was created under the wrong name. Say which record is expected.
3. **Does it hold the right value?** Name the wrong value: an old address, a Cloudflare proxy address (the proxy is switched on), or a conflicting AAAA or CNAME record.
4. **Is it only a delay?** The name servers are right but public resolvers do not see it yet. Say it will fix itself and roughly when, from the record's cache lifetime.

Public resolvers are asked only once the domain's own name servers hold the right record. Asking them about a name that does not exist yet makes them remember "no such name" for the zone's negative lifetime, which delays the record after it is created. That delay is what made the earlier waits so long.

Each result carries: a short title, what was found, what it means, what to do and who does it (the operator or the client), and how to confirm it is fixed. A result is one of **correct**, **will fix itself** (with an expected time) or **needs action**.

### 3.3 A problem blocks only what depends on it, and the run tells you

- Each deploy step has one of four plain states: **Done**, **Working** (with an expected time), **Needs action** (with the diagnosis and a Try again button) or **Waiting on another step** (naming which).
- The step order puts everything that does not need DNS first: check credentials, create the server, wait for it, prepare it, install the CRM, fix file ownership. Then DNS, then the certificate, then the final checks, then registering the instance.
- The run waits for DNS only as long as the diagnosis says the problem will fix itself, and never longer than fifteen minutes. A problem that will not fix itself is reported at once, not after a timeout.
- A run that reaches the end with something outstanding ends as **Needs action**, not as failed. The instance is registered, and the outstanding steps become open items on it.
- The progress window shows a clear message at the top when a step needs action, with the diagnosis. The detailed log stays below it.
- **Try again** resumes at the first step that is not done, without creating another server. It accepts a corrected web address. When the CRM is already installed, the run applies the new address to the installed CRM before continuing.

### 3.4 The certificate finishes itself, and the operator can check at any time

- When DNS is not correct by the end of the run, the run installs a **self-healing job on the server**. Every fifteen minutes the job:
  1. checks that the domain's own DNS host holds the record, then that public resolvers return the server's own address for the web address, and stops there if not;
  2. asks Let's Encrypt for a test certificate (a dry run that issues nothing), and stops there if that fails, keeping the reason;
  3. only then switches the installed CRM to its secure mode with a real certificate, using the EspoCRM installer's own reinstall path that keeps the data;
  4. removes itself once the certificate is in place.

  Each run of the job writes its outcome to a status file on the server. The job never takes the CRM down unless the test certificate has already succeeded.
- **Open items** live on the instance, not on the run, and survive until closed. Each has a title, what is needed, who acts, and how to confirm.
- A **Check DNS now** button on the instance runs the diagnostic, reads the self-healing job's status from the server, runs the job at once when DNS is correct, and updates the open items. When the certificate is in place, the open items close and the instance's address becomes its secure address.

### 3.5 The wizard is larger, easier to read, and explains itself

- The wizard opens large (about three quarters of the screen), can be resized, and has three columns: the list of steps on the left, the questions in the middle, and a help panel on the right that explains the field in use.
- Text uses the application's larger sizes: page titles at the second heading size, questions at the large body size, explanations at body size in normal contrast.
- Pages: **Before you start** → **Web address** → **DNS** → **Server** → **Administrator** → **Review**.
  - Before you start lists what to have ready and roughly how long a deploy takes.
  - Every page opens with one sentence on why the step exists. Every field has a question-style label, an example, and what happens if it is wrong.
  - Server sizes are shown in plain words with their monthly cost, the recommended size pre-selected, and one supported operating system image rather than the whole catalogue.
  - Review is a formatted summary, not a text box.
- Progress uses sentences with expected times ("Installing the CRM — about 6 minutes"), not internal step names.
- At the end, a **handover sheet** that can be saved as a file gives: the web address and the server's IP address; the DNS record to create, in place, action, expected result and what-if form, tailored to the detected DNS host; how to verify it worked; a troubleshooting list of symptom, cause and fix; the administrator login with a copy button; and what happens next, including not logging in before the padlock appears.

## 4. Out of scope for this build

- Deploying onto a server the client already has. Discussed, not yet decided.
- Creating records automatically at DNS hosts other than Cloudflare. Manual DNS covers them.
- A reserved IP address that survives a rebuild. Discussed as a later improvement.
- Hosting the wizard as a page inside the main window, saved drafts, and an application-wide text-size setting.

## 5. How the certificate is completed — verified facts

These were read from the EspoCRM installer, version 2.8.1, on 09-23-26. They have not yet been proven on a live server.

- The installer's plain web mode serves the site on port 80 and sets the site address to `http://` plus the domain. Its web-server configuration does not block `/.well-known/acme-challenge/`, so a Let's Encrypt web-root challenge can be answered from the host folder `data/espocrm/ephemeral/public` while the CRM is running.
- The installer's `command.sh cert-generate` works only in its Let's Encrypt mode, because only that mode's container setup includes the certificate tool.
- Running the installer again on an existing installation, without the clean option, performs a reinstall that keeps the database and files. It reads the existing passwords from the running setup and switches mode. With `--ssl --letsencrypt` it obtains the certificate. **If the certificate request fails partway, the CRM is left stopped.** This is why the self-healing job runs a dry-run certificate request first.
- The server preparation step opens ports 22, 80 and 443 in the server's firewall.

## 6. Decisions made while building

- **The instance is recorded at its secure address from the start.** The requirement for Check DNS now says the recorded address switches to https once the certificate is in place. It is recorded as https from the start instead, so CRMBuilder never sends the administrator password over plain HTTP. Open items say the certificate is outstanding until it is. This departs from the wording of REQ-651 and needs the product owner's agreement.
- **Where open items are kept.** On the instance's deploy configuration, which is already the one place that holds a deployed server's management facts.
- **When the install uses the certificate.** If DNS already points at the server when the install starts (normal in Cloudflare DNS mode, because the record is created before the server is prepared), the CRM is installed with its certificate in one pass, as before. Only otherwise is the plain web mode used.
- **The wizard layout.** A large, resizable window with the three columns, rather than a page inside the main window. The in-window page was listed as out of scope.

## 7. Terms introduced

These were used and agreed in the design discussion. Each needs a glossary entry.

- **Cloudflare DNS mode** and **manual DNS** are existing terms (manual DNS: REQ-642, DEC-1146) and are used here unchanged. Revision 1.0 of this document coined "automatic DNS" and "DNS instructions" for the same two things; those names are withdrawn.
- **Needs action:** the state of a deploy step or a deploy run that cannot continue until a person does something.
- **Open item:** something outstanding on an instance, with what is needed, who acts and how to confirm.
- **Self-healing job:** the scheduled job installed on a new server that completes the certificate once DNS is correct.
- **Check DNS now:** the instance action that re-runs the DNS diagnostic and the self-healing job.
- **Handover sheet:** the saved summary given to the client at the end of a deploy.

## Change log

| Revision | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.2 | 09-23-26 21:25 | Claude (Claude Code) | The diagnostic and the self-healing job ask the domain's own DNS host before public resolvers, so they never cause the delay they report. |
| 1.1 | 09-23-26 21:10 | Claude (Claude Code) | Record identifiers added. The two DNS modes use the existing terms Cloudflare DNS mode and manual DNS. Added section 6, decisions made while building. |
| 1.0 | 09-23-26 20:40 | Claude (Claude Code), with Doug Bower | First version, from the SES-432 discussion. |
