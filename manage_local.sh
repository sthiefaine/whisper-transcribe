#!/bin/bash

echo "🍎 Gestion du service Whisper sur Docker local (MacBook)"
echo "=" * 50

case "$1" in
    "start")
        echo "🚀 Démarrage du service..."
        chmod +x run_local_mac.sh
        ./run_local_mac.sh
        ;;
    "stop")
        echo "🛑 Arrêt du service..."
        docker-compose -f docker-compose.local.yml down
        ;;
    "restart")
        echo "🔄 Redémarrage du service..."
        docker-compose -f docker-compose.local.yml down
        sleep 5
        chmod +x run_local_mac.sh
        ./run_local_mac.sh
        ;;
    "logs")
        echo "📊 Affichage des logs..."
        docker-compose -f docker-compose.local.yml logs -f whisper-api
        ;;
    "status")
        echo "📊 Statut du service..."
        docker-compose -f docker-compose.local.yml ps
        ;;
    "clean")
        echo "🧹 Nettoyage complet..."
        docker-compose -f docker-compose.local.yml down -v
        docker system prune -f
        docker volume prune -f
        ;;
    "nginx")
        echo "🌐 Démarrage avec nginx..."
        docker-compose -f docker-compose.local.yml --profile nginx up -d
        echo "✅ Nginx démarré sur http://localhost:8090"
        ;;
    "models")
        echo "📥 Gestion des modèles..."
        chmod +x download_models.sh
        if [ -z "$2" ]; then
            echo "📋 Modèles disponibles:"
            echo "  base, small, medium, large-v1, large-v2, large-v3"
            echo ""
            echo "Usage: $0 models <nom_du_modele>"
            echo "Exemple: $0 models large-v3"
        else
            ./download_models.sh "$2"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|logs|status|clean|nginx|models}"
        echo ""
        echo "Commandes disponibles:"
        echo "  start   - Démarrer le service"
        echo "  stop    - Arrêter le service"
        echo "  restart - Redémarrer le service"
        echo "  logs    - Afficher les logs"
        echo "  status  - Vérifier le statut"
        echo "  clean   - Nettoyer complètement"
        echo "  nginx   - Démarrer avec nginx"
        echo "  models  - Télécharger des modèles"
        echo ""
        echo "Exemples:"
        echo "  $0 start         # Démarrer le service"
        echo "  $0 logs          # Voir les logs en temps réel"
        echo "  $0 status        # Vérifier le statut"
        echo "  $0 models large-v3  # Télécharger le modèle large-v3"
        exit 1
        ;;
esac 