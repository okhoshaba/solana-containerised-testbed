package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	"solana-latency-research/internal/utils"
)

func main() {
	// 该脚本用于快速验证 Yellowstone gRPC 连通性，避免干扰主进程。
	cfg, err := utils.LoadConfig("configs/config.example.yaml")
	if err != nil {
		log.Fatalf("加载配置失败: %v", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	conn, err := grpc.DialContext(
		ctx,
		cfg.GRPC,
		grpc.WithBlock(),
		grpc.WithReturnConnectionError(),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		log.Fatalf("gRPC 连通性检查失败: %v", err)
	}
	defer conn.Close()

	fmt.Println("Yellowstone gRPC 连通性检查成功")
}
