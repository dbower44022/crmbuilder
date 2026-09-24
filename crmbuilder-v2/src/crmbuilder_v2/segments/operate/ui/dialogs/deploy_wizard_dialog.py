"""Deploy wizard — PI-419 (REQ-522, DEC-945); manual DNS PI-566 (REQ-642);
redesigned by PI-571 (REQ-648, REQ-652).

A large, resizable window in three columns: the steps on the left, the
questions in the middle, and on the right a help panel that explains whichever
field is in use. Six pages collect what a deploy run needs and queue it:

1. **Before you start** — what to have ready, and whether the DigitalOcean
   credential (required) and the Cloudflare credential (optional) are set.
2. **Web address** — the full address first. The wizard looks up who hosts
   its DNS and whether the name already points somewhere.
3. **DNS** — who creates the record: CRMBuilder in Cloudflare (offered only
   when the address is in a Cloudflare zone this engagement's credential can
   edit, and that zone is the one the internet uses), or by hand (manual DNS).
   Either way the CRM is installed without waiting for DNS.
4. **Server** — the instance's name, a size described in plain words with its
   monthly cost (the recommended one pre-selected), the region, and extra SSH
   keys. The operating system is the one supported image, not a choice.
5. **Administrator** — the CRM's first login, and the email for certificate
   notices (the administrator's unless another is given).
6. **Review** — a formatted summary of what will happen; Deploy queues the
   run and emits :attr:`run_queued`.

Next is never disabled (GVR-217): a page that is not complete explains what is
missing when Next is clicked. All network calls run off the UI thread.
"""

from __future__ import annotations

import html
import logging
import secrets as _random
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.segments.operate.ui.dialogs.handover_dialog import fit_to_screen
from crmbuilder_v2.segments.operate.ui.dialogs.provider_credentials_dialog import (
    ProviderCredentialsDialog,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    RequestShapeError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.widgets.form_helpers import primary_button, required_label
from crmbuilder_v2.ui.workers import drain_workers, run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.deploy_wizard_dialog")

PAGE_START, PAGE_ADDRESS, PAGE_DNS, PAGE_SERVER, PAGE_ACCOUNTS, PAGE_REVIEW = range(6)
_PAGE_TITLES = ("Before you start", "Web address", "DNS", "Server", "Administrator", "Review")
#: One sentence per page on why the step exists (REQ-652).
_PAGE_WHY = (
    "A deploy rents a server, installs the CRM on it, and connects it to a web address. "
    "This page lists what to have ready.",
    "This is the address your staff will type to reach the CRM.",
    "One DNS record points the web address at the new server. This page decides who creates it.",
    "The server is the computer, rented from DigitalOcean, that runs the CRM.",
    "The administrator is the first person who can sign in to the CRM.",
    "Check the details. Deploy starts the work on the CRMBuilder service; you can close "
    "the progress window at any time.",
)

DNS_MODE_CLOUDFLARE, DNS_MODE_MANUAL = "cloudflare", "manual"

#: The size pre-selected when the catalog offers it.
RECOMMENDED_SIZE = "s-2vcpu-4gb"
#: The sizes offered unless "Show every size" is ticked.
OFFERED_SIZES = ("s-1vcpu-2gb", "s-2vcpu-4gb", "s-4vcpu-8gb")
#: The one operating system image CRMBuilder supports.
SUPPORTED_IMAGE = "ubuntu-24-04-x64"
#: The region pre-selected when the catalog offers it.
DEFAULT_REGION = "nyc3"

_WIZARD_STYLE = """
QLabel {{ font-size: {large}; }}
QLineEdit, QComboBox, QListWidget, QCheckBox, QRadioButton {{ font-size: {large}; }}
QLineEdit, QComboBox {{ min-height: 30px; }}
QLabel[role="hint"] {{ font-size: {body}; color: {hint}; }}
QLabel[role="finding"] {{ font-size: {large}; border-radius: 6px; padding: 10px; background: {panel}; }}
"""


def generate_password(length: int = 20) -> str:
    """A URL-safe random password an administrator can paste anywhere."""
    return _random.token_urlsafe(length)[:length]


def describe_size(size: dict[str, Any]) -> str:
    """A server size in plain words: processors, memory and monthly cost."""
    vcpus = size.get("vcpus") or 0
    memory_gb = (size.get("memory") or 0) / 1024
    text = f"{vcpus} processor{'s' if vcpus != 1 else ''}, {memory_gb:g} GB memory"
    price = size.get("price_monthly")
    if price is not None:
        text += f" — ${price:g} a month"
    if size.get("slug") == RECOMMENDED_SIZE:
        text += "  (recommended)"
    return text


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "hint")
    label.setWordWrap(True)
    return label


class DeployWizardDialog(QDialog):
    """Collect a provisioning request and queue it as a deploy run."""

    #: Emitted with the new run's identifier after a successful queue.
    run_queued = Signal(str)
    connection_lost = Signal(str)

    def __init__(self, client, parent=None) -> None:
        super().__init__(parent)
        self._client = client
        self._in_flight: list = []
        self._providers: dict[str, dict[str, Any]] = {}
        self._options: dict[str, Any] = {}
        self._zones: list[dict[str, Any]] = []
        self._lookup: dict[str, Any] | None = None
        self._lookup_for = ""
        self._lookup_error = ""
        self._advance_after_lookup = False
        #: Set once the operator picks a DNS option, so it is not overridden.
        self._dns_choice_made = False
        self._help: dict[QObject, str] = {}
        self.setWindowTitle("Deploy a new CRM instance")
        fit_to_screen(self, 0.75, (980, 680))
        self.setStyleSheet(_WIZARD_STYLE.format(
            large=t("font.size.body_large"), body=t("font.size.body"),
            hint=t("color.neutral.700"), panel=t("color.neutral.100"),
        ))

        outer = QVBoxLayout(self)
        body = QHBoxLayout()
        outer.addLayout(body, 1)

        self._step_list = QListWidget()
        self._step_list.setObjectName("wizard_steps")
        self._step_list.setFixedWidth(210)
        self._step_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._step_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for i, title in enumerate(_PAGE_TITLES, start=1):
            self._step_list.addItem(QListWidgetItem(f"{i}. {title}"))
        body.addWidget(self._step_list)

        centre = QVBoxLayout()
        self._title = QLabel("")
        self._title.setObjectName("wizard_title")
        self._title.setStyleSheet(f"font-size: {t('font.size.heading_2')}; font-weight: 600;")
        centre.addWidget(self._title)
        self._why = QLabel("")
        self._why.setObjectName("wizard_why")
        self._why.setWordWrap(True)
        centre.addWidget(self._why)
        self._pages = QStackedWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self._pages)
        centre.addWidget(scroll, 1)
        self._notice = QLabel("")
        self._notice.setObjectName("wizard_notice")
        self._notice.setWordWrap(True)
        self._notice.setStyleSheet(f"color: {t('color.warning.default')}; font-weight: 600;")
        centre.addWidget(self._notice)
        body.addLayout(centre, 1)

        self._help_view = QTextBrowser()
        self._help_view.setObjectName("wizard_help")
        self._help_view.setFixedWidth(330)
        self._help_view.setStyleSheet(
            f"font-size: {t('font.size.body')}; background: {t('color.neutral.50')};"
        )
        body.addWidget(self._help_view)

        nav = QHBoxLayout()
        nav.addStretch(1)
        self._back_btn = QPushButton("Back")
        self._back_btn.setObjectName("wizard_back")
        self._back_btn.clicked.connect(self._back)
        self._next_btn = primary_button("Next")
        self._next_btn.setObjectName("wizard_next")
        self._next_btn.clicked.connect(self._next)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("wizard_cancel")
        cancel_btn.clicked.connect(self.reject)
        nav.addWidget(cancel_btn)
        nav.addWidget(self._back_btn)
        nav.addWidget(self._next_btn)
        outer.addLayout(nav)

        self._pages.addWidget(self._build_start_page())
        self._pages.addWidget(self._build_address_page())
        self._pages.addWidget(self._build_dns_page())
        self._pages.addWidget(self._build_server_page())
        self._pages.addWidget(self._build_accounts_page())
        self._pages.addWidget(self._build_review_page())
        self._show_page(PAGE_START)
        self._load_providers()

    # -- help panel ----------------------------------------------------------

    def _explain(self, widget: QWidget, text: str) -> None:
        """Show ``text`` in the help panel whenever ``widget`` has focus."""
        self._help[widget] = text
        widget.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.FocusIn and watched in self._help:
            self._help_view.setHtml(self._help[watched])
        return super().eventFilter(watched, event)

    def _page_help(self, index: int) -> str:
        texts = {
            PAGE_START: (
                "<h3>How a deploy works</h3><p>CRMBuilder rents a server from DigitalOcean, "
                "prepares it, installs the CRM, and registers it as an instance.</p>"
                "<p><b>DNS never stops the install.</b> If the web address does not point at "
                "the server yet, the CRM is installed anyway and the security certificate is "
                "added automatically once it does.</p><p>If something needs a person, the "
                "progress window says what, who, and how to check it is fixed.</p>"
            ),
            PAGE_ADDRESS: (
                "<h3>Choosing the address</h3><p>Use a subdomain such as "
                "<b>crm.yourdomain.org</b>. The bare domain usually hosts the organisation's "
                "website, and pointing it at the CRM would take the website down.</p>"
                "<p>The wizard asks the internet who hosts DNS for the domain. That company is "
                "where the record has to be created.</p>"
            ),
            PAGE_DNS: (
                "<h3>Who creates the record</h3><p><b>CRMBuilder</b> can create it only when the "
                "domain's DNS is in Cloudflare, in an account this engagement's Cloudflare "
                "credential can edit.</p><p>Otherwise it is created <b>by hand</b> at the "
                "domain's DNS host. The progress window and the handover sheet give the exact "
                "record. Nothing waits for it.</p>"
            ),
            PAGE_SERVER: (
                "<h3>Choosing a size</h3><p>The recommended size suits a small organisation's "
                "CRM. A size can be changed later in DigitalOcean.</p>"
            ),
            PAGE_ACCOUNTS: (
                "<h3>The administrator</h3><p>This login is also what CRMBuilder uses to audit "
                "and publish to the CRM. Record the password now; it is stored encrypted and "
                "not shown again, except on the handover sheet for this deploy.</p>"
            ),
            PAGE_REVIEW: (
                "<h3>After Deploy</h3><p>The progress window shows each step with its expected "
                "time. You can close it; the run continues and appears under Deploy History."
                "</p><p>At the end, open the <b>handover sheet</b> and save it for the client.</p>"
            ),
        }
        return texts.get(index, "")

    # -- pages -------------------------------------------------------------

    def _build_start_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        checklist = QLabel(
            "<p><b>Have these ready:</b></p><ul>"
            "<li>The <b>web address</b> the CRM will use, such as crm.yourdomain.org.</li>"
            "<li>Whether you can <b>edit that domain's DNS</b>. If you cannot, the person "
            "who can will add one record; the wizard gives the exact instructions.</li>"
            "<li>An <b>email address</b> for the CRM's administrator.</li>"
            "<li>About <b>20 minutes</b>. Nothing needs watching: you can close the progress "
            "window and come back.</li></ul>"
        )
        checklist.setWordWrap(True)
        v.addWidget(checklist)
        form = QFormLayout()
        self._do_status = QLabel("Checking…")
        self._do_status.setObjectName("wizard_do_status")
        self._cf_status = QLabel("Checking…")
        self._cf_status.setObjectName("wizard_cf_status")
        form.addRow("DigitalOcean (required)", self._do_status)
        form.addRow("Cloudflare (optional)", self._cf_status)
        v.addLayout(form)
        v.addWidget(_hint(
            "DigitalOcean provides the server. Cloudflare is needed only if CRMBuilder is to "
            "create the DNS record itself."
        ))
        btn = QPushButton("Set credentials…")
        btn.setObjectName("wizard_set_credentials")
        btn.clicked.connect(self._open_credentials)
        v.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
        v.addStretch(1)
        return page

    def _build_address_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(required_label("What web address should the CRM use?"))
        row = QHBoxLayout()
        self.full_address = QLineEdit()
        self.full_address.setObjectName("wizard_full_address")
        self.full_address.setPlaceholderText("crm.yourdomain.org")
        self.full_address.textChanged.connect(self._address_edited)
        self._explain(self.full_address, (
            "<h3>Web address</h3><p>Example: <b>crm.clevelandbusinessmentors.org</b>.</p>"
            "<p>If it is wrong, visitors reach the wrong place. It can be corrected later "
            "without rebuilding the server, but the certificate is then issued again.</p>"
        ))
        row.addWidget(self.full_address, 1)
        self._lookup_btn = QPushButton("Check this address")
        self._lookup_btn.setObjectName("wizard_lookup")
        self._lookup_btn.clicked.connect(self.start_lookup)
        row.addWidget(self._lookup_btn)
        v.addLayout(row)
        v.addWidget(_hint(
            "Example: crm.clevelandbusinessmentors.org. Use a subdomain, the part before "
            "the domain; the bare domain usually hosts the website."
        ))
        self.address_result = QLabel("")
        self.address_result.setObjectName("wizard_address_result")
        self.address_result.setProperty("role", "finding")
        self.address_result.setWordWrap(True)
        self.address_result.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(self.address_result)
        v.addStretch(1)
        return page

    def _build_dns_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(QLabel("Who will create the DNS record?"))
        self._dns_group = QButtonGroup(self)
        self.dns_cloudflare = QRadioButton("CRMBuilder creates it in Cloudflare")
        self.dns_cloudflare.setObjectName("wizard_dns_cloudflare")
        self.dns_manual = QRadioButton("It is created by hand at the domain's DNS host (manual DNS)")
        self.dns_manual.setObjectName("wizard_dns_manual")
        self._dns_group.addButton(self.dns_cloudflare)
        self._dns_group.addButton(self.dns_manual)
        self.dns_manual.setChecked(True)
        for button in (self.dns_cloudflare, self.dns_manual):
            button.clicked.connect(lambda _checked=False: setattr(self, "_dns_choice_made", True))
        v.addWidget(self.dns_cloudflare)
        self._cloudflare_note = _hint("")
        self._cloudflare_note.setObjectName("wizard_cloudflare_note")
        v.addWidget(self._cloudflare_note)
        v.addWidget(self.dns_manual)
        v.addWidget(_hint(
            "Once the server has its IP address, CRMBuilder shows the exact record to create "
            "and puts it on the handover sheet. The CRM is installed without waiting for it, "
            "and the certificate is added automatically once the record works."
        ))
        for button, text in (
            (self.dns_cloudflare, "<h3>CRMBuilder creates the record</h3><p>The record is "
             "created DNS only (no Cloudflare proxy), so the certificate check and SSH reach "
             "the server. An existing record for the name is never overwritten.</p>"),
            (self.dns_manual, "<h3>Manual DNS</h3><p>Whoever can sign in to the domain's DNS "
             "host adds one record: type A, the name, and the server's IP address. The "
             "handover sheet says exactly how and how to check it worked.</p>"),
        ):
            self._explain(button, text)
        v.addStretch(1)
        return page

    def _build_server_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.instance_name = QLineEdit()
        self.instance_name.setObjectName("wizard_instance_name")
        self.instance_name.setPlaceholderText("Cleveland Business Mentors CRM")
        form.addRow(required_label("What should CRMBuilder call this CRM?"), self.instance_name)
        form.addRow("", _hint("Shown in CRMBuilder's list of instances. It does not appear to the CRM's users."))
        self._explain(self.instance_name, "<h3>Instance name</h3><p>How this CRM appears in "
                      "CRMBuilder, for example <b>Cleveland Business Mentors CRM</b>.</p>")
        self.size = QComboBox()
        self.size.setObjectName("wizard_size")
        form.addRow(required_label("How large a server?"), self.size)
        self.all_sizes = QCheckBox("Show every size")
        self.all_sizes.setObjectName("wizard_all_sizes")
        self.all_sizes.toggled.connect(self._refresh_sizes)
        form.addRow("", self.all_sizes)
        self._explain(self.size, "<h3>Server size</h3><p>The recommended size runs a small "
                      "organisation's CRM comfortably. Too small makes the CRM slow; too large "
                      "only costs more. It can be changed later in DigitalOcean.</p>")
        self.region = QComboBox()
        self.region.setObjectName("wizard_region")
        self.region.currentIndexChanged.connect(self._refresh_sizes)
        form.addRow(required_label("Where should the server be?"), self.region)
        form.addRow("", _hint("Choose the region nearest the people who will use the CRM."))
        self._explain(self.region, "<h3>Region</h3><p>The DigitalOcean data centre the server "
                      "runs in. Nearer is faster for the people using the CRM.</p>")
        self.image = QComboBox()
        self.image.setObjectName("wizard_image")
        self.image.setVisible(False)
        self._image_label = QLabel("—")
        self._image_label.setObjectName("wizard_image_label")
        form.addRow("Operating system", self._image_label)
        self.ssh_keys = QListWidget()
        self.ssh_keys.setObjectName("wizard_ssh_keys")
        self.ssh_keys.setMaximumHeight(120)
        form.addRow("Extra SSH keys (optional)", self.ssh_keys)
        form.addRow("", _hint(
            "The run makes its own key for the server. Tick an account key only if someone "
            "must also be able to sign in to the server directly."
        ))
        return page

    def _build_accounts_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.admin_username = QLineEdit("admin")
        self.admin_username.setObjectName("wizard_admin_username")
        form.addRow(required_label("Administrator username"), self.admin_username)
        self.admin_email = QLineEdit()
        self.admin_email.setObjectName("wizard_admin_email")
        self.admin_email.setPlaceholderText("admin@yourdomain.org")
        form.addRow(required_label("Administrator email"), self.admin_email)
        self._explain(self.admin_email, "<h3>Administrator email</h3><p>Where the CRM sends "
                      "the administrator's password resets and notices.</p>")
        pw_row = QHBoxLayout()
        self.admin_password = QLineEdit()
        self.admin_password.setObjectName("wizard_admin_password")
        self.admin_password.setEchoMode(QLineEdit.EchoMode.Password)
        gen = QPushButton("Generate")
        gen.setObjectName("wizard_generate_password")
        gen.clicked.connect(lambda: self.admin_password.setText(generate_password()))
        copy = QPushButton("Copy")
        copy.setObjectName("wizard_copy_password")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.admin_password.text()))
        show = QCheckBox("Show")
        show.toggled.connect(
            lambda on: self.admin_password.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        pw_row.addWidget(self.admin_password, 1)
        pw_row.addWidget(gen)
        pw_row.addWidget(copy)
        pw_row.addWidget(show)
        form.addRow(required_label("Administrator password"), pw_row)
        form.addRow("", _hint(
            "At least 8 characters. Record it now in a password manager; it appears once more, "
            "on this deploy's handover sheet."
        ))
        self._explain(self.admin_password, "<h3>Password</h3><p>Generate makes a strong one. "
                      "It is stored encrypted for CRMBuilder's own audits and publishing.</p>")
        self.letsencrypt_email = QLineEdit()
        self.letsencrypt_email.setObjectName("wizard_letsencrypt_email")
        self.letsencrypt_email.setPlaceholderText("Same as the administrator email")
        form.addRow("Email for certificate notices", self.letsencrypt_email)
        form.addRow("", _hint("Let's Encrypt, which issues the certificate, writes here if it "
                              "is about to expire. Leave empty to use the administrator email."))
        self.auto_db = QCheckBox("Generate database passwords automatically (recommended)")
        self.auto_db.setObjectName("wizard_auto_db")
        self.auto_db.setChecked(True)
        self.auto_db.toggled.connect(self._toggle_db_fields)
        form.addRow("", self.auto_db)
        self.db_password = QLineEdit()
        self.db_password.setObjectName("wizard_db_password")
        self.db_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.db_root_password = QLineEdit()
        self.db_root_password.setObjectName("wizard_db_root_password")
        self.db_root_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Database password", self.db_password)
        form.addRow("Database root password", self.db_root_password)
        self._toggle_db_fields(True)
        return page

    def _build_review_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        self.review = QTextBrowser()
        self.review.setObjectName("wizard_review")
        self.review.setStyleSheet(f"font-size: {t('font.size.body_large')};")
        v.addWidget(self.review, 1)
        return page

    # -- navigation --------------------------------------------------------

    def _show_page(self, index: int) -> None:
        self._pages.setCurrentIndex(index)
        self._title.setText(f"Step {index + 1} of {len(_PAGE_TITLES)} — {_PAGE_TITLES[index]}")
        self._why.setText(_PAGE_WHY[index])
        self._notice.setText("")
        self._help_view.setHtml(self._page_help(index))
        for i in range(self._step_list.count()):
            item = self._step_list.item(i)
            font = item.font()
            font.setBold(i == index)
            item.setFont(font)
            prefix = "✓ " if i < index else ("▸ " if i == index else "   ")
            item.setText(f"{prefix}{i + 1}. {_PAGE_TITLES[i]}")
        self._back_btn.setVisible(index > PAGE_START)
        self._next_btn.setText("Deploy" if index == PAGE_REVIEW else "Next")
        if index == PAGE_DNS:
            self._apply_dns_choices()
        if index == PAGE_REVIEW:
            self.review.setHtml(self.render_review_html())

    @property
    def page(self) -> int:
        return self._pages.currentIndex()

    def _back(self) -> None:
        if self.page > PAGE_START:
            self._show_page(self.page - 1)

    def _next(self) -> None:
        if self.page == PAGE_ADDRESS and self._lookup_for != self.address():
            if "." in self.address():
                self._advance_after_lookup = True
                self.start_lookup()
                return
        problem = self.validate_page(self.page)
        if problem:
            self._notice.setText(problem)
            return
        if self.page == PAGE_REVIEW:
            self._deploy()
            return
        self._show_page(self.page + 1)

    def validate_page(self, index: int) -> str | None:
        """Return what is missing on ``index``, or ``None`` when it is complete."""
        if index == PAGE_START:
            if not self._configured("digitalocean"):
                return "Set the DigitalOcean credential first (Set credentials…)."
        elif index == PAGE_ADDRESS:
            if "." not in self.address():
                return "Enter the CRM's full web address, for example crm.yourdomain.org."
        elif index == PAGE_DNS:
            if self.dns_cloudflare.isChecked() and not self._cloudflare_zone():
                return "CRMBuilder cannot create this record in Cloudflare; choose manual DNS."
        elif index == PAGE_SERVER:
            if not self.instance_name.text().strip():
                return "Give the instance a name."
            if not (self.region.currentData() and self.size.currentData() and self.image.currentData()):
                return "Choose a size and a region (the DigitalOcean catalog must have loaded)."
        elif index == PAGE_ACCOUNTS:
            if not self.admin_username.text().strip():
                return "Enter the administrator username."
            if "@" not in self.admin_email.text():
                return "Enter the administrator email."
            if len(self.admin_password.text()) < 8:
                return "Enter an administrator password of at least 8 characters (or Generate one)."
            other = self.letsencrypt_email.text().strip()
            if other and "@" not in other:
                return "The email for certificate notices is not an email address."
        return None

    # -- the address and its DNS -------------------------------------------

    def address(self) -> str:
        """The CRM's full web address as entered, normalised."""
        return self.full_address.text().strip().lower().rstrip(".")

    @property
    def manual_dns(self) -> bool:
        """Whether the record is created by hand (manual DNS)."""
        return not self.dns_cloudflare.isChecked()

    @property
    def dns_mode(self) -> str:
        return DNS_MODE_MANUAL if self.manual_dns else DNS_MODE_CLOUDFLARE

    def _address_edited(self) -> None:
        if self.address() != self._lookup_for:
            self.address_result.setText("")

    def start_lookup(self) -> None:
        """Ask the service who hosts DNS for the address (off the UI thread)."""
        domain = self.address()
        if "." not in domain:
            self._notice.setText("Enter the CRM's full web address, for example crm.yourdomain.org.")
            return
        self._notice.setText(f"Checking who hosts DNS for {domain}…")
        self._lookup_btn.setEnabled(False)
        self._in_flight.append(
            run_in_thread(
                lambda: self._client.lookup_deploy_address(domain),
                on_success=lambda result: self.apply_lookup(domain, result),
                on_error=lambda exc: self._lookup_failed(domain, exc),
                parent=self,
            )
        )

    def apply_lookup(self, domain: str, result: dict[str, Any]) -> None:
        """Show what the address lookup found (public so tests can feed one)."""
        self._lookup_btn.setEnabled(True)
        self._lookup, self._lookup_for, self._lookup_error = result or {}, domain, ""
        self._notice.setText("")
        self.address_result.setText(self._lookup_html())
        self._apply_dns_choices()
        if self._advance_after_lookup:
            self._advance_after_lookup = False
            if self.page == PAGE_ADDRESS:
                self._next()

    def _lookup_failed(self, domain: str, exc: Exception) -> None:
        self._lookup_btn.setEnabled(True)
        self._advance_after_lookup = False
        if isinstance(exc, RequestShapeError):
            problems = "; ".join(e.get("message", "") for e in (exc.errors or [])) or str(exc)
            self._notice.setText(problems)
            return
        if isinstance(exc, StorageConnectionError):
            self.connection_lost.emit(str(exc))
        # The lookup is advice, not a gate: a failed lookup lets the operator go on.
        self._lookup, self._lookup_for, self._lookup_error = {}, domain, str(exc)
        self.address_result.setText(
            "<b>Could not look up this address</b> — " + html.escape(str(exc))
            + ". You can still continue; the deploy checks DNS again later."
        )
        self._notice.setText("")

    def _lookup_html(self) -> str:
        info = self._lookup or {}
        domain = html.escape(info.get("domain") or self._lookup_for)
        if not info.get("zone"):
            return (
                f"<b>No DNS host answers for {domain}.</b> Check the spelling. If the domain "
                "was registered today it may not be active yet. You can continue; the address "
                "can be corrected later without rebuilding the server."
            )
        host = html.escape(info.get("dns_host") or "an unknown DNS host")
        zone = html.escape(info["zone"])
        lines = [f"DNS for <b>{zone}</b> is hosted by <b>{host}</b>."]
        if self._cloudflare_zone():
            lines.append("That zone is in CRMBuilder's Cloudflare account, so CRMBuilder can "
                         "create the record.")
        else:
            lines.append(f"The record will be created by hand at {host}; the wizard gives the "
                         "exact instructions.")
        existing = info.get("existing_records") or {}
        if existing:
            found = "; ".join(f"{k} {', '.join(v)}" for k, v in existing.items())
            lines.append(
                f"<br><b>This name is already in use</b> ({html.escape(found)}). If something is "
                "running there, choose another name. CRMBuilder never overwrites an existing "
                "record."
            )
        return " ".join(lines)

    def _cloudflare_zone(self) -> dict[str, Any] | None:
        """The Cloudflare zone CRMBuilder can edit for this address, if any."""
        info = self._lookup or {}
        zone = info.get("zone")
        if not zone or not info.get("uses_cloudflare") or not self._configured("cloudflare"):
            return None
        return next((z for z in self._zones if z.get("name") == zone), None)

    def _apply_dns_choices(self) -> None:
        zone = self._cloudflare_zone()
        self.dns_cloudflare.setEnabled(zone is not None)
        info = self._lookup or {}
        if zone is not None:
            self._cloudflare_note.setText(
                f"Available: {zone['name']} is in CRMBuilder's Cloudflare account and is the "
                "zone the internet uses."
            )
            if not self._lookup_error and not self._dns_choice_made:
                self.dns_cloudflare.setChecked(True)
        else:
            if not self._configured("cloudflare"):
                why = "no Cloudflare credential is set for this engagement."
            elif not info.get("zone"):
                why = "the address has not been looked up, or no DNS host answers for it."
            elif not info.get("uses_cloudflare"):
                why = f"DNS for {info['zone']} is hosted by {info.get('dns_host')}, not Cloudflare."
            else:
                why = f"{info['zone']} is not in CRMBuilder's Cloudflare account."
            self._cloudflare_note.setText("Not available: " + why)
            self.dns_manual.setChecked(True)

    # -- data --------------------------------------------------------------

    def build_body(self) -> dict[str, Any]:
        """The POST /deploy-runs body for the current inputs."""
        email = self.admin_email.text().strip()
        body: dict[str, Any] = {
            "instance_name": self.instance_name.text().strip(),
            "region": self.region.currentData(),
            "size": self.size.currentData(),
            "image": self.image.currentData(),
            "ssh_key_ids": [
                self.ssh_keys.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.ssh_keys.count())
                if self.ssh_keys.item(i).checkState() == Qt.CheckState.Checked
            ],
            "dns_mode": self.dns_mode,
            "letsencrypt_email": self.letsencrypt_email.text().strip() or email,
            "admin_username": self.admin_username.text().strip(),
            "admin_email": email,
            "admin_password": self.admin_password.text(),
        }
        zone = None if self.manual_dns else self._cloudflare_zone()
        if zone is None:
            body["dns_mode"] = DNS_MODE_MANUAL
            body["domain"] = self.address()
        else:
            body["zone_id"] = zone["id"]
            body["zone_name"] = zone["name"]
            body["subdomain"] = self.address()[: -len(zone["name"]) - 1]
        if not self.auto_db.isChecked():
            if self.db_password.text():
                body["db_password"] = self.db_password.text()
            if self.db_root_password.text():
                body["db_root_password"] = self.db_root_password.text()
        return body

    def render_review_html(self) -> str:
        b = self.build_body()
        e = html.escape
        size = next((s for s in self._options.get("sizes", []) if s.get("slug") == b["size"]), {})
        keys = ", ".join(str(k) for k in b["ssh_key_ids"]) or "none (the run's own key only)"
        dns = (
            "CRMBuilder creates the record in Cloudflare."
            if b["dns_mode"] == DNS_MODE_CLOUDFLARE
            else "Manual DNS: the record is created by hand. The progress window and the "
                 "handover sheet show exactly what to create."
        )
        db = "generated by the service" if self.auto_db.isChecked() else "as entered"
        return (
            f"<h2>{e(b['instance_name'])}</h2>"
            "<table cellpadding='4'>"
            f"<tr><td>Web address</td><td><b>https://{e(self.address())}</b></td></tr>"
            f"<tr><td>DNS</td><td>{e(dns)}</td></tr>"
            f"<tr><td>Server</td><td>{e(describe_size(size) if size else str(b['size']))}, "
            f"in {e(self.region.currentText())}</td></tr>"
            f"<tr><td>Operating system</td><td>{e(self.image.currentText())}</td></tr>"
            f"<tr><td>Extra SSH keys</td><td>{e(keys)}</td></tr>"
            f"<tr><td>Administrator</td><td>{e(b['admin_username'])} &lt;{e(b['admin_email'])}&gt;</td></tr>"
            f"<tr><td>Certificate notices</td><td>{e(b['letsencrypt_email'])}</td></tr>"
            f"<tr><td>Database passwords</td><td>{db}</td></tr></table>"
            "<h3>What happens after Deploy</h3><ol>"
            "<li>The server is created and started — about 3 minutes.</li>"
            "<li>The server is prepared and the CRM installed — about 12 minutes.</li>"
            "<li>DNS is checked. If it is not ready, you are told what to do and by whom; "
            "the CRM stays installed.</li>"
            "<li>The certificate is added — at once if DNS is ready, otherwise automatically "
            "within 15 minutes of it becoming ready.</li>"
            "<li>The instance appears in CRMBuilder, with any open items listed on it.</li></ol>"
        )

    def render_review(self) -> str:
        """The review as plain text (kept for callers that want text)."""
        doc = QTextBrowser()
        doc.setHtml(self.render_review_html())
        return doc.toPlainText()

    # -- loading -------------------------------------------------------------

    def _load_providers(self) -> None:
        self._in_flight.append(
            run_in_thread(
                self._client.list_provider_credentials,
                on_success=self._providers_loaded,
                on_error=self._on_error,
                parent=self,
            )
        )

    def _providers_loaded(self, records: list[dict[str, Any]]) -> None:
        self._providers = {r["provider"]: r for r in records or []}
        for key, label in (("digitalocean", self._do_status), ("cloudflare", self._cf_status)):
            rec = self._providers.get(key)
            if rec and rec.get("configured"):
                label.setText("✓ Configured" + (f" — {rec['label']}" if rec.get("label") else ""))
                label.setStyleSheet(f"color: {t('color.success.default')};")
            else:
                label.setText("Not set")
                label.setStyleSheet(f"color: {t('color.warning.default')};")
        self._load_catalogs()

    def _configured(self, provider: str) -> bool:
        return bool((self._providers.get(provider) or {}).get("configured"))

    def _load_catalogs(self) -> None:
        if self._configured("digitalocean"):
            self._in_flight.append(
                run_in_thread(
                    self._client.get_digitalocean_options,
                    on_success=self.apply_options,
                    on_error=self._on_error,
                    parent=self,
                )
            )
        if self._configured("cloudflare"):
            self._in_flight.append(
                run_in_thread(
                    self._client.list_cloudflare_zones,
                    on_success=self.apply_zones,
                    on_error=self._on_error,
                    parent=self,
                )
            )

    def apply_options(self, options: dict[str, Any]) -> None:
        """Populate the server page from a DigitalOcean catalog payload."""
        self._options = options or {}
        self.region.blockSignals(True)
        self.region.clear()
        for r in self._options.get("regions", []):
            self.region.addItem(f"{r.get('name')} ({r['slug']})", r["slug"])
        default = self.region.findData(DEFAULT_REGION)
        self.region.setCurrentIndex(default if default >= 0 else 0)
        self.region.blockSignals(False)
        self.image.clear()
        for i in self._options.get("images", []):
            self.image.addItem(i.get("name") or i["slug"], i["slug"])
        supported = self.image.findData(SUPPORTED_IMAGE)
        if supported < 0:
            supported = next(
                (n for n in range(self.image.count()) if "ubuntu" in str(self.image.itemData(n))), 0
            )
        self.image.setCurrentIndex(supported)
        self._image_label.setText(
            f"{self.image.currentText()} — the operating system CRMBuilder supports"
            if self.image.count() else "—"
        )
        self.ssh_keys.clear()
        for k in self._options.get("ssh_keys", []):
            item = QListWidgetItem(f"{k.get('name')} ({k.get('fingerprint')})")
            item.setData(Qt.ItemDataRole.UserRole, k["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.ssh_keys.addItem(item)
        self._refresh_sizes()

    def _refresh_sizes(self) -> None:
        region = self.region.currentData()
        current = self.size.currentData()
        self.size.clear()
        sizes = [
            s for s in self._options.get("sizes", [])
            if not (region and s.get("regions") and region not in s["regions"])
        ]
        offered = [s for s in sizes if s.get("slug") in OFFERED_SIZES]
        shown = sizes if (self.all_sizes.isChecked() or not offered) else offered
        for s in shown:
            self.size.addItem(describe_size(s), s["slug"])
        for wanted in (current, RECOMMENDED_SIZE):
            index = self.size.findData(wanted)
            if wanted and index >= 0:
                self.size.setCurrentIndex(index)
                break

    def apply_zones(self, zones: list[dict[str, Any]]) -> None:
        self._zones = zones or []
        if self._lookup is not None:
            self.address_result.setText(self._lookup_html())
            self._apply_dns_choices()

    def _toggle_db_fields(self, auto: bool) -> None:
        self.db_password.setVisible(not auto)
        self.db_root_password.setVisible(not auto)

    def _open_credentials(self) -> None:
        dialog = ProviderCredentialsDialog(self._client, parent=self)
        dialog.connection_lost.connect(self.connection_lost)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
        self._load_providers()

    def done(self, result: int) -> None:  # noqa: D401 - Qt override
        """Finish the in-flight workers before the dialog is torn down."""
        drain_workers(self._in_flight)
        super().done(result)

    # -- deploy --------------------------------------------------------------

    def _deploy(self) -> None:
        self._next_btn.setEnabled(False)
        body = self.build_body()
        self._in_flight.append(
            run_in_thread(
                lambda: self._client.create_deploy_run(body),
                on_success=self._queued,
                on_error=self._deploy_failed,
                parent=self,
            )
        )

    def _queued(self, run: dict[str, Any]) -> None:
        ident = run.get("deploy_run_identifier") or ""
        self.run_queued.emit(ident)
        self.accept()

    def _deploy_failed(self, exc: Exception) -> None:
        self._next_btn.setEnabled(True)
        if isinstance(exc, RequestShapeError):
            problems = "; ".join(
                f"{e.get('field')}: {e.get('message')}" for e in (exc.errors or [])
            ) or str(exc)
            self._notice.setText(f"Not queued — {problems}")
            return
        self._on_error(exc)

    def _on_error(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            self.connection_lost.emit(str(exc))
        _log.warning("deploy wizard: %s", exc)
        detail = str(getattr(exc, "errors", "")) if isinstance(exc, StorageClientError) else None
        ErrorDialog(
            title="Deploy wizard", message=str(exc), detail=detail or None, parent=self
        ).exec()
