#!/usr/bin/env python3
"""Script de test et d'analyse pour la génération d'article avec chronométrage détaillé."""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

import httpx


class ArticleGenerationAnalyzer:
    """Analyseur de performance pour la génération d'article."""
    
    def __init__(self, api_url: str = "http://localhost:8000/api/v1"):
        self.api_url = api_url
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.status_history: List[Dict] = []
        self.step_timings: Dict[str, float] = {}
        self.last_status: Optional[str] = None
        self.last_progress: int = 0
        self.last_step: Optional[str] = None
    
    async def test_generation(
        self,
        topic: str,
        keywords: str,
        tone: str = "professional",
        target_words: int = 2000,
        language: str = "fr",
        generate_images: bool = True,
        site_profile_id: Optional[int] = None,
    ) -> Dict:
        """Teste la génération d'article avec analyse détaillée."""
        
        request_data = {
            "topic": topic,
            "keywords": keywords,
            "tone": tone,
            "target_words": target_words,
            "language": language,
            "generate_images": generate_images,
        }
        
        if site_profile_id is not None:
            request_data["site_profile_id"] = site_profile_id
        
        print("=" * 90)
        print("🧪 TEST ET ANALYSE DE GÉNÉRATION D'ARTICLE")
        print("=" * 90)
        print(f"\n📋 Paramètres de la requête:")
        print(json.dumps(request_data, indent=2, ensure_ascii=False))
        print(f"\n⏰ Démarrage: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        async with httpx.AsyncClient(timeout=600.0) as client:
            # 1. Lancer la génération
            print(f"\n🚀 [ÉTAPE 1] Lancement de la génération...")
            launch_start = time.time()
            
            try:
                response = await client.post(
                    f"{self.api_url}/articles/generate",
                    json=request_data,
                )
                launch_time = time.time() - launch_start
                
                if response.status_code != 202:
                    print(f"❌ Erreur HTTP {response.status_code}: {response.text}")
                    return {"error": response.text, "status_code": response.status_code}
                
                result = response.json()
                plan_id = result["plan_id"]
                print(f"✅ Génération lancée en {launch_time:.2f}s")
                print(f"   Plan ID: {plan_id}")
                
            except httpx.ConnectError:
                print("❌ Erreur: Impossible de se connecter à l'API")
                print("   Assurez-vous que le serveur est démarré: make start")
                return {"error": "Connection failed"}
            except Exception as e:
                print(f"❌ Erreur lors du lancement: {e}")
                return {"error": str(e)}
            
            # 2. Surveiller le statut avec chronométrage
            print(f"\n⏳ [ÉTAPE 2] Surveillance du statut...")
            self.start_time = time.time()
            max_wait = 600  # 10 minutes max
            
            previous_status = None
            previous_step = None
            step_start_time = None
            
            while time.time() - self.start_time < max_wait:
                check_start = time.time()
                status_response = await client.get(
                    f"{self.api_url}/articles/{plan_id}/status"
                )
                check_time = time.time() - check_start
                
                if status_response.status_code != 200:
                    print(f"❌ Erreur lors de la récupération du statut: {status_response.status_code}")
                    break
                
                status_data = status_response.json()
                status = status_data["status"]
                progress = status_data.get("progress_percentage", 0)
                current_step = status_data.get("current_step", "")
                elapsed = time.time() - self.start_time
                
                # Détecter les changements d'étape
                if current_step != previous_step and previous_step is not None:
                    if step_start_time is not None:
                        step_duration = time.time() - step_start_time
                        self.step_timings[previous_step] = step_duration
                        print(f"\n   ⏱️  Durée de '{previous_step}': {step_duration:.2f}s")
                
                if status != previous_status or current_step != previous_step:
                    step_start_time = time.time()
                    self.status_history.append({
                        "timestamp": elapsed,
                        "status": status,
                        "progress": progress,
                        "step": current_step,
                    })
                    
                    print(f"\n📊 [{elapsed:6.1f}s] Statut: {status:12s} | Progression: {progress:3d}% | Étape: {current_step}")
                
                previous_status = status
                previous_step = current_step
                
                if status == "validated":
                    self.end_time = time.time()
                    if step_start_time is not None:
                        step_duration = self.end_time - step_start_time
                        self.step_timings[current_step] = step_duration
                    print(f"\n✅ Génération terminée avec succès!")
                    break
                elif status == "failed":
                    self.end_time = time.time()
                    print(f"\n❌ Génération échouée")
                    if "error_message" in status_data:
                        print(f"   Erreur: {status_data['error_message']}")
                    break
                
                await asyncio.sleep(3)  # Attendre 3 secondes avant le prochain check
            
            if self.end_time is None:
                self.end_time = time.time()
                print(f"\n⚠️  Timeout atteint ({max_wait}s)")
            
            # 3. Récupérer les détails complets
            print(f"\n📄 [ÉTAPE 3] Récupération des détails...")
            detail_response = await client.get(f"{self.api_url}/articles/{plan_id}")
            
            article_detail = None
            if detail_response.status_code == 200:
                article_detail = detail_response.json()
            
            # 4. Générer le rapport d'analyse
            return self._generate_report(plan_id, article_detail, request_data)
    
    def _generate_report(
        self,
        plan_id: str,
        article_detail: Optional[Dict],
        request_data: Dict,
    ) -> Dict:
        """Génère un rapport d'analyse détaillé."""
        
        total_time = (self.end_time - self.start_time) if self.start_time else 0
        
        print(f"\n{'=' * 90}")
        print("📊 RAPPORT D'ANALYSE DE PERFORMANCE")
        print("=" * 90)
        
        # Résumé général
        print(f"\n📋 RÉSUMÉ GÉNÉRAL")
        print(f"   Plan ID: {plan_id}")
        print(f"   Topic: {request_data.get('topic')}")
        print(f"   Durée totale: {total_time:.2f}s ({total_time/60:.2f} minutes)")
        print(f"   Nombre de vérifications de statut: {len(self.status_history)}")
        
        # Analyse par étape
        print(f"\n⏱️  CHRONOMÉTRAGE PAR ÉTAPE")
        if self.step_timings:
            total_steps_time = sum(self.step_timings.values())
            for step, duration in sorted(self.step_timings.items(), key=lambda x: x[1], reverse=True):
                percentage = (duration / total_steps_time * 100) if total_steps_time > 0 else 0
                print(f"   {step:30s}: {duration:6.2f}s ({percentage:5.1f}%)")
        else:
            print("   Aucune étape chronométrée")
        
        # Historique des statuts
        print(f"\n📈 HISTORIQUE DES STATUTS")
        for i, entry in enumerate(self.status_history, 1):
            print(f"   [{i:2d}] {entry['timestamp']:6.1f}s | {entry['status']:12s} | {entry['progress']:3d}% | {entry['step']}")
        
        # Détails de l'article
        if article_detail:
            print(f"\n📄 DÉTAILS DE L'ARTICLE")
            print(f"   Status: {article_detail.get('status')}")
            print(f"   Topic: {article_detail.get('topic')}")
            
            # Images
            images = article_detail.get("images", [])
            print(f"\n🖼️  IMAGES GÉNÉRÉES: {len(images)}")
            for idx, img in enumerate(images, 1):
                print(f"\n   Image #{idx}:")
                print(f"      ID: {img.get('id')}")
                print(f"      Type: {img.get('image_type')}")
                print(f"      Chemin: {img.get('local_path')}")
                print(f"      Alt text: {img.get('alt_text', 'N/A')}")
            
            # Métriques de qualité
            quality_metrics = article_detail.get("quality_metrics")
            if quality_metrics:
                print(f"\n📊 MÉTRIQUES DE QUALITÉ")
                print(f"   {json.dumps(quality_metrics, indent=6, ensure_ascii=False)}")
        
        # Analyse des performances
        print(f"\n🔍 ANALYSE DES PERFORMANCES")
        
        # Identifier l'étape la plus lente
        if self.step_timings:
            slowest_step = max(self.step_timings.items(), key=lambda x: x[1])
            print(f"   Étape la plus lente: '{slowest_step[0]}' ({slowest_step[1]:.2f}s)")
        
        # Estimation du temps de génération d'images
        if request_data.get("generate_images"):
            print(f"\n   ⚠️  Génération d'images activée")
            print(f"      Temps estimé pour images: 90-180 secondes (1.5-3 minutes)")
            print(f"      Cette étape est généralement la plus longue du processus")
        
        # Recommandations
        print(f"\n💡 RECOMMANDATIONS")
        if total_time > 300:  # Plus de 5 minutes
            print(f"   ⚠️  La génération a pris plus de 5 minutes")
            print(f"      - Vérifiez les logs pour identifier les goulots d'étranglement")
            print(f"      - Considérez réduire le nombre d'images générées")
            print(f"      - Vérifiez la performance de l'API Ideogram")
        
        if request_data.get("generate_images") and total_time > 180:
            print(f"   🖼️  Optimisation images:")
            print(f"      - La génération d'images peut être optimisée")
            print(f"      - Considérez réduire target_valid_images de 3 à 1-2")
            print(f"      - Vérifiez que le GPU est utilisé pour la critique vision")
        
        print(f"\n{'=' * 90}")
        
        return {
            "plan_id": plan_id,
            "total_time": total_time,
            "step_timings": self.step_timings,
            "status_history": self.status_history,
            "article_detail": article_detail,
        }


async def main():
    """Point d'entrée principal."""
    analyzer = ArticleGenerationAnalyzer()
    
    # Paramètres de test fournis par l'utilisateur
    result = await analyzer.test_generation(
        topic="Stratégies de contenu B2B pour les solutions d'intelligence artificielle",
        keywords="intelligence artificielle, IA, B2B, automatisation, data, machine learning, stratégie de contenu",
        tone="professional",
        target_words=2000,
        language="fr",
        generate_images=True,
        site_profile_id=20,
    )
    
    if "error" in result:
        print(f"\n❌ Test échoué: {result.get('error')}")
        return 1
    
    print(f"\n✅ Test terminé avec succès!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)












