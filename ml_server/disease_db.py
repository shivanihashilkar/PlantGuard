"""Disease metadata for the 38 supported PlantVillage classes."""

CLASS_LABELS = [
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___Cedar_apple_rust",
    "Apple___healthy",
    "Blueberry___healthy",
    "Cherry___Powdery_mildew",
    "Cherry___healthy",
    "Corn___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn___Common_rust",
    "Corn___Northern_Leaf_Blight",
    "Corn___healthy",
    "Grape___Black_rot",
    "Grape___Esca_(Black_Measles)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)",
    "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)",
    "Peach___Bacterial_spot",
    "Peach___healthy",
    "Pepper,_bell___Bacterial_spot",
    "Pepper,_bell___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Raspberry___healthy",
    "Soybean___healthy",
    "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch",
    "Strawberry___healthy",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]

SUPPORTED_PLANTS = sorted({label.split("___", 1)[0].replace("_", " ") for label in CLASS_LABELS})

SPECIFIC_CAUSES = {
    "Apple_scab": "Fungal infection caused by Venturia inaequalis",
    "Black_rot": "Fungal infection that forms dark lesions and fruit rot",
    "Cedar_apple_rust": "Fungal rust disease that alternates between apple and cedar hosts",
    "Powdery_mildew": "Fungal growth on the leaf surface",
    "Cercospora_leaf_spot Gray_leaf_spot": "Fungal leaf spot disease",
    "Common_rust": "Fungal rust disease",
    "Northern_Leaf_Blight": "Fungal leaf blight disease",
    "Esca_(Black_Measles)": "Grape trunk disease complex",
    "Leaf_blight_(Isariopsis_Leaf_Spot)": "Fungal grape leaf spot and blight disease",
    "Haunglongbing_(Citrus_greening)": "Bacterial citrus greening disease spread by psyllids",
    "Bacterial_spot": "Bacterial leaf and fruit spot",
    "Early_blight": "Fungal blight commonly caused by Alternaria species",
    "Late_blight": "Oomycete disease caused by Phytophthora infestans",
    "Leaf_Mold": "Fungal disease favored by humid conditions",
    "Septoria_leaf_spot": "Fungal leaf spot disease",
    "Spider_mites Two-spotted_spider_mite": "Mite pest damage",
    "Target_Spot": "Fungal leaf spot disease",
    "Tomato_Yellow_Leaf_Curl_Virus": "Viral disease spread mainly by whiteflies",
    "Tomato_mosaic_virus": "Viral disease spread by seed, tools, and contact",
    "Leaf_scorch": "Fungal leaf scorch disease",
}


def _plant(label):
    return label.split("___", 1)[0].replace("_", " ")


def _condition(label):
    return label.split("___", 1)[1]


def _display(condition):
    if condition == "healthy":
        return "Healthy"
    return condition.replace("_", " ")


def _metadata(label):
    plant = _plant(label)
    condition = _condition(label)
    display_name = _display(condition)

    if condition == "healthy":
        return {
            "display_name": "Healthy",
            "plant": plant,
            "cause": "None",
            "severity": "None",
            "severity_pct": 0,
            "status_color": "safe",
            "symptoms": ["No visible disease symptoms detected in the matched class."],
            "treatment": ["No treatment required. Continue normal monitoring and care."],
            "prevention": [
                "Inspect leaves regularly.",
                "Avoid long periods of leaf wetness.",
                "Keep good spacing and airflow around plants.",
            ],
        }

    cause = SPECIFIC_CAUSES.get(condition, "Plant disease or pest stress matched by the model")
    return {
        "display_name": display_name,
        "plant": plant,
        "cause": cause,
        "severity": "Moderate",
        "severity_pct": 65,
        "status_color": "warning",
        "symptoms": [
            "Leaf spots, discoloration, scorch, curling, or blight-like patches may be present.",
            "Compare the uploaded leaf with the top matched class before applying treatment.",
        ],
        "treatment": [
            "Remove heavily affected leaves and dispose of them away from healthy plants.",
            "Use a crop-appropriate fungicide, bactericide, or pest control when symptoms match.",
            "Avoid overhead watering while the plant recovers.",
        ],
        "prevention": [
            "Use disease-free planting material.",
            "Sanitize pruning tools after use.",
            "Improve airflow and avoid overcrowding.",
            "Rotate crops where practical.",
        ],
    }


DISEASE_DATABASE = {label: _metadata(label) for label in CLASS_LABELS}
