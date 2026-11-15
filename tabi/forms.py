from django import forms
from django.utils.text import slugify
from .models import Profile, Interest, Post, Comment, Community

class ProfileForm(forms.ModelForm):
    interests = forms.ModelMultipleChoiceField(queryset=Interest.objects.all(), required=False, widget=forms.CheckboxSelectMultiple)
    custom_interests = forms.CharField(
        required=False,
        max_length=400,
        label="Add your own interests",
        help_text="Separate interests with commas, for example: Hiking, Baking, Film photography.",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Add interests, separated by commas"}),
    )
    class Meta:
        model = Profile
        fields = ["bio", "picture", "location", "interests"]
    def clean_picture(self):
        image = self.cleaned_data.get("picture")
        if image and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Image must be 5 MB or smaller.")
        if image and image.content_type not in ("image/jpeg", "image/png", "image/webp"):
            raise forms.ValidationError("Use a JPG, PNG, or WebP image.")
        return image

    def clean_custom_interests(self):
        value = self.cleaned_data["custom_interests"]
        for name in (part.strip() for part in value.split(",")):
            if name and (len(name) > 60 or not slugify(name)):
                raise forms.ValidationError("Each interest must be 60 characters or fewer and include a letter or number.")
        return value

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["content", "image"]
    def clean_content(self):
        value = self.cleaned_data["content"].strip()
        if not value: raise forms.ValidationError("Write something before posting.")
        return value
    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and image.size > 5 * 1024 * 1024: raise forms.ValidationError("Image must be 5 MB or smaller.")
        if image and image.content_type not in ("image/jpeg", "image/png", "image/webp"): raise forms.ValidationError("Use a JPG, PNG, or WebP image.")
        return image

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["content"]
    def clean_content(self): return self.cleaned_data["content"].strip()

class CommunityForm(forms.ModelForm):
    class Meta:
        model = Community
        fields = ["name", "slug", "description", "interests"]
        widgets = {"interests": forms.CheckboxSelectMultiple}
    def clean_slug(self):
        slug = slugify(self.cleaned_data["slug"] or self.cleaned_data.get("name", ""))
        return slug
