from django.views.generic import TemplateView

class ComponentsView(TemplateView):
    template_name = "pages/components/components.html"  # Path to the components template

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Static data representing the fields
        context["fields"] = {
            "Name": "Structural Assembly",
            "Country": "India",
            "Surface": "Metal",
            "Public": "Yes"            
        }
        # static country list of testing purpose
        context["countries"] = ["India", "Indonesia", "Germany"]
        return context
    
    def post(self, request, *args, **kwargs):
        import json
        # Process the incoming JSON data
        data = json.loads(request.body)
        # For now, just return the received data (in a real app, save it somewhere)
        return JsonResponse({"status": "success", "data": data})