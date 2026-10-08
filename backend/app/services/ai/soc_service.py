from typing import Dict, Any, Optional

class SOCService:
    """
    Soil Organic Carbon (SOC) Verification Modality.
    Evaluates farmer-reported and laboratory sample soil metrics (SOC %, Depth, Soil Classification)
    against agro-ecological benchmark baselines.
    
    Standard agricultural SOC benchmarks:
    - SOC > 2.0% -> High carbon retention (Score 80-100)
    - SOC 1.2% - 2.0% -> Moderate to Good (Score 65-80)
    - SOC 0.6% - 1.2% -> Fair / Typical tropical baseline (Score 50-65)
    - SOC < 0.6% -> Low / Depleted (Score < 50)
    """

    SOIL_TYPE_FACTORS = {
        "Black Soil": 1.10,      # High clay, high organic retention
        "Loam": 1.05,            # Ideal texture
        "Alluvial": 1.00,        # Fertile riverine
        "Red Soil": 0.95,        # Moderate
        "Red Sandy Loam": 0.92,
        "Sandy Loam": 0.90,
        "Clay": 1.02,
        "Sandy": 0.82            # Low retention
    }

    @classmethod
    def evaluate_soc(
        cls,
        soc_pct: Optional[float] = None,
        soil_depth_cm: Optional[float] = None,
        soil_type: Optional[str] = None
    ) -> Dict[str, Any]:
        if soc_pct is None or not isinstance(soc_pct, (int, float)) or soc_pct <= 0 or soc_pct > 10:
            return {
                "soc_pct": None,
                "soc_score": None,
                "soil_status": "NOT PROVIDED",
                "baseline_benchmark": "No soil laboratory or field test data provided.",
                "provided": False,
                "reason": "Soil organic carbon data is required for soil verification."
            }

        # Soil type adjusts the score slightly (retention capacity). Unknown types use a neutral 1.0.
        soil_factor = cls.SOIL_TYPE_FACTORS.get(soil_type, 1.0) if soil_type else 1.0

        # Base SOC score from percentage
        if soc_pct >= 2.2:
            base_score = 85.0 + min(15.0, (soc_pct - 2.2) * 12.0)
            status = "Optimal Carbon Density (High Sequestration)"
        elif soc_pct >= 1.5:
            base_score = 70.0 + ((soc_pct - 1.5) / 0.7) * 15.0
            status = "Good Organic Content (Active Micro-Biomass)"
        elif soc_pct >= 0.8:
            base_score = 52.0 + ((soc_pct - 0.8) / 0.7) * 18.0
            status = "Moderate Baseline (Developing Agro-Ecosystem)"
        else:
            base_score = max(15.0, (soc_pct / 0.8) * 52.0)
            status = "Depleted Organic Carbon (Requires Regeneration)"
            
        final_score = round(max(10.0, min(100.0, base_score * (0.9 + 0.1 * soil_factor))), 1)
        
        return {
            "soc_pct": round(soc_pct, 2),
            "soc_score": final_score,
            "soil_status": status,
            "baseline_benchmark": (
                f"{soil_type} profile (soil factor {soil_factor})" if soil_type
                else "Soil type not provided (neutral soil factor 1.0)"
            ),
            "soil_factor": soil_factor,
            "provided": True,
            "depth_analyzed_cm": soil_depth_cm,
            "soil_type": soil_type
        }
