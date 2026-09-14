from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, TextAreaField, SelectField,
    DecimalField, IntegerField, SubmitField,
)
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange


class RegisterForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")]
    )
    referral_code = StringField("Referral code (optional)", validators=[Optional(), Length(max=16)])
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Log in")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send reset link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirm new password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")]
    )
    submit = SubmitField("Reset password")


class ProfileForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    country = StringField("Country", validators=[Optional(), Length(max=80)])
    phone = StringField("Phone", validators=[Optional(), Length(max=40)])
    submit = SubmitField("Save changes")


class ReferralVerificationForm(FlaskForm):
    submitted_reference = StringField(
        "Reference (e.g. broker account number)", validators=[DataRequired(), Length(max=255)]
    )
    submit = SubmitField("Submit for review")


class ProductForm(FlaskForm):
    code = StringField("Product code", validators=[DataRequired(), Length(max=64)])
    name = StringField("Name", validators=[DataRequired(), Length(max=150)])
    slug = StringField("Slug (URL)", validators=[DataRequired(), Length(max=150)])
    tagline = StringField("Tagline", validators=[Optional(), Length(max=255)])
    short_description = TextAreaField("Short description", validators=[Optional(), Length(max=500)])
    description = TextAreaField("Full description", validators=[Optional()])
    features = TextAreaField("Features (one per line)", validators=[Optional()])

    status = SelectField("Status", choices=[("draft", "Draft"), ("live", "Live"), ("retired", "Retired")])
    display_order = IntegerField("Display order", validators=[Optional(), NumberRange(min=0)], default=0)

    price = DecimalField("Price", validators=[Optional(), NumberRange(min=0)], places=2)
    currency = StringField("Currency", validators=[Optional(), Length(max=10)], default="USD")
    purchase_url = StringField("Purchase / checkout URL (optional, rarely used)", validators=[Optional(), Length(max=500)])
    telegram_url = StringField(
        "Telegram contact for purchases (optional — overrides site default)",
        validators=[Optional(), Length(max=300)],
    )

    free_access_enabled = BooleanField("Free access via affiliate route enabled")
    affiliate_requirements = TextAreaField("Affiliate requirements (shown to users)", validators=[Optional()])

    version = StringField("Version", validators=[Optional(), Length(max=40)])
    platform = StringField("Platform (e.g. MT4 / MT5)", validators=[Optional(), Length(max=40)])
    download_url = StringField("Download URL", validators=[Optional(), Length(max=500)])
    license_required = BooleanField("License required", default=True)

    submit = SubmitField("Save product")


class LicenseIssueForm(FlaskForm):
    user_email = StringField("User email", validators=[DataRequired(), Email()])
    product_id = SelectField("Product", coerce=int, validators=[DataRequired()])
    access_method = SelectField(
        "Access method",
        choices=[("purchase", "Purchase"), ("affiliate", "Affiliate / free access"), ("admin_grant", "Admin grant")],
    )
    max_activations = IntegerField("Max activations (blank = unlimited)", validators=[Optional(), NumberRange(min=1)])
    submit = SubmitField("Issue license")


class UserSearchForm(FlaskForm):
    q = StringField("Search users", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Search")
